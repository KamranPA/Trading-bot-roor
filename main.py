# ---------------------------------------------------------
# FILE PATH: main.py (v8.2 - Optimized for GitHub Actions & 11 Pairs)
# ---------------------------------------------------------
import os
import sys
import logging
import sqlite3
import threading
import datetime
from concurrent.futures import ThreadPoolExecutor

# تنظیم دقیق مسیر ریشه پروژه
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    import config
    from src import database, coinex_client, strategy, telegram_bot, indicators, optimizer
    from src.brain import TradingBrain
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BRAIN = TradingBrain()
db_lock = threading.Lock()

def heartbeat_job():
    """ارسال گزارش زنده بودن سیستم به تلگرام"""
    try:
        watchlist_count = len(getattr(config, 'WATCHLIST', []))
        models_dir = os.path.join(BASE_DIR, "src", "models")
        model_count = len([f for f in os.listdir(models_dir) if f.endswith('.pkl')]) if os.path.exists(models_dir) else 0
        
        telegram_bot.send_heartbeat_report(watchlist_count, model_count)
        logging.info("✅ گزارش Heartbeat با موفقیت ارسال شد.")
    except Exception as e:
        logging.error(f"خطا در ارسال گزارش Heartbeat: {e}")

def process_pair(pair):
    try:
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty: 
            return

        df = indicators.calculate_indicators(df)
        
        # نکته: فیلتر ۸ ساعته از اینجا حذف شد تا مستقیماً در strategy.py و با آگاهی از جهتِ ورود چک شود
        signal = strategy.generate_signal(df, pair, model=BRAIN)
        
        with db_lock:
            if signal:
                database.save_signal_advanced(pair=pair, **signal)
                database.log_scan_status(pair, "SIGNAL SENT")
                telegram_bot.format_and_send_signal(signal)
            else:
                database.log_scan_status(pair, "nosignal")
    except Exception as e:
        logging.error(f"خطا در پردازش {pair}: {e}")

def run_auto_optimization():
    db_path = database.DB_PATH 
    try:
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT count(*) FROM signals").fetchone()[0]
            
            # اجرای Optimizer اگر تعداد سیگنال‌ها ضریبی از 50 باشد
            if count > 0 and count % 50 == 0:
                logging.info("⚙️ سیستم به حد نصاب رسید: اجرای پروسه ارتقای خودکار...")
                optimizer.optimize_all(mode="live")
    except Exception as e:
        logging.error(f"خطا در پروسه خودارتقایی: {e}")

def run_bot():
    logging.info("🤖 اسکنر هوشمند v8.2 (پشتیبانی موازی ۱۱ ارز) فعال شد.")
    database.init_db()
    
    try:
        database.manage_open_positions()
    except Exception as e:
        logging.error(f"خطا در مدیریت پوزیشن‌ها: {e}")
    
    # ۱. اجرای بهینه‌ساز پیش از شروع اسکن
    run_auto_optimization()
    
    # ۲. پردازش تمام ارزها به صورت موازی 
    watchlist = getattr(config, 'WATCHLIST', [])
    # تعداد workers به 12 افزایش یافت تا هر 11 ارز بدون معطلی و در یک لحظه پردازش شوند
    with ThreadPoolExecutor(max_workers=12) as executor:
        executor.map(process_pair, watchlist)

if __name__ == "__main__":
    # در محیط GitHub Actions نیازی به schedule و حلقه بی‌نهایت نیست
    # خود گیت‌هاب بر اساس فایل run_bot.yml این اسکریپت را زمان‌بندی می‌کند
    
    # ارسال Heartbeat فقط اگر ساعت 22:00 تا 22:59 (به وقت سرور ابری) باشد تا از اسپم جلوگیری شود
    current_hour = datetime.datetime.utcnow().hour
    if current_hour == 22:
        heartbeat_job()
        
    # اجرای اصلی ربات
    run_bot()

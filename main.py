# ---------------------------------------------------------
# FILE PATH: main.py (v8.0 - Multi-Model Architecture)
# ---------------------------------------------------------
import os
import sys
import logging
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

# تنظیم دقیق مسیر ریشه پروژه برای اطمینان از Import شدن ماژول‌ها
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

# تنظیمات لاگینگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# مقداردهی به مغز متفکر هوش مصنوعی (مدیریت‌کننده و توزیع‌کننده مدل‌های اختصاصی هر ارز)
BRAIN = TradingBrain()

# تعریف قفل سراسری برای جلوگیری از تداخل در دیتابیس (Thread Safety)
db_lock = threading.Lock()

def process_pair(pair):
    """پردازش تک‌جفت ارز و مدیریت جریان سیگنال‌دهی"""
    try:
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty: 
            return

        df = indicators.calculate_indicators(df)
        
        # ۱. بررسی فیلترهای استراتژی
        if strategy.is_blocked_by_8h_filter(pair):
            with db_lock:
                database.log_scan_status(pair, "blocked for 8h filter")
            logging.info(f"⛔️ مسدود توسط فیلتر ۸ ساعته: {pair}")
            return

        # ۲. تولید سیگنال با مغز متفکر هوشمند (پاس دادن BRAIN به جای مدل استاتیک قبلی)
        signal = strategy.generate_signal(df, pair, model=BRAIN)
        
        with db_lock:
            if signal:
                database.save_signal_advanced(pair=pair, **signal)
                database.log_scan_status(pair, "SIGNAL SENT")
                telegram_bot.format_and_send_signal(signal)
                logging.info(f"✅ سیگنال برای {pair} ارسال شد.")
            else:
                database.log_scan_status(pair, "nosignal")
                logging.info(f"⚪️ فاقد سیگنال برای {pair}")
            
    except Exception as e:
        logging.error(f"خطا در پردازش {pair}: {e}")

def run_auto_optimization():
    """بررسی خودکار برای بهینه‌سازی پارامترها (اکنون به صورت تفکیک‌شده برای هر ارز)"""
    # فراخوانی مسیر دیتابیس از ماژول database (منبع حقیقت)
    db_path = database.DB_PATH 
    try:
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT count(*) FROM signals").fetchone()[0]
            if count > 0 and count % 50 == 0:
                logging.info(f"🚀 شروع ارتقای هوشمند (تعداد کل سیگنال‌ها: {count})")
                optimizer.optimize_all(mode="live")
    except Exception as e:
        logging.error(f"خطا در پروسه خودارتقایی: {e}")

def run_bot():
    """تابع اصلی اجرای ربات"""
    logging.info("🤖 اسکنر هوشمند v8.0 (Multi-Model) فعال شد.")
    
    # اطمینان از ایجاد دیتابیس و جداول پیش از هر عملیات
    database.init_db()
    
    try:
        database.manage_open_positions()
    except Exception as e:
        logging.error(f"خطا در مدیریت پوزیشن‌ها: {e}")
    
    run_auto_optimization()
    
    # اجرای موازی برای تمام ارزهای لیست شده در config
    watchlist = getattr(config, 'WATCHLIST', [])
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_pair, watchlist)

if __name__ == "__main__":
    run_bot()

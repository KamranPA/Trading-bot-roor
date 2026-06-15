# ---------------------------------------------------------
# FILE PATH: main.py (نسخه نهایی و اصلاح شده - رفع خطای TypeError آرگومان)
# ---------------------------------------------------------
import os
import sys
import logging
import sqlite3
import threading
import datetime
from concurrent.futures import ThreadPoolExecutor

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

def check_exits():
    """
    تابع بررسی قیمت و بستن پوزیشن‌ها در صورت رسیدن به حد سود یا ضرر.
    ورودی ندارد و کاملاً مستقل از واچ‌لیست کار می‌کند.
    """
    try:
        positions = database.get_open_positions() 
        if not positions:
            return

        for pos in positions:
            try:
                # استخراج ایمن داده‌ها بر اساس ایندکس دیتابیس (id, timestamp, symbol, direction, entry, sl, tp1, tp2)
                sig_id = pos[0]
                symbol = pos[2]
                direction = pos[3]
                entry = float(pos[4])
                sl = float(pos[5])
                tp2 = float(pos[7])
                
                # دریافت کندل جاری از صرافی
                df = coinex_client.get_coinex_candles(symbol, limit=2)
                if df is None or df.empty: 
                    continue
                
                # بررسی هوشمند ستون قیمت برای جلوگیری از KeyError
                if 'Close' in df.columns:
                    current_price = float(df.iloc[-1]['Close'])
                elif 'close' in df.columns:
                    current_price = float(df.iloc[-1]['close'])
                else:
                    current_price = float(df.iloc[-1].iloc[4])

                # منطق خروج هوشمند
                pnl = 0.0
                should_close = False
                
                if direction == "LONG":
                    if current_price <= sl: 
                        pnl = ((sl - entry) / entry) * 100
                        should_close = True
                    elif current_price >= tp2: 
                        pnl = ((tp2 - entry) / entry) * 100
                        should_close = True
                elif direction == "SHORT":
                    if current_price >= sl: 
                        pnl = ((entry - sl) / entry) * 100
                        should_close = True
                    elif current_price <= tp2: 
                        pnl = ((entry - tp2) / entry) * 100
                        should_close = True
                
                if should_close:
                    with db_lock:
                        database.update_position_status(sig_id, 'CLOSED', pnl)
                    logging.info(f"✅ پوزیشن {symbol} بسته شد. سود/ضرر: {pnl:.2f}%")
                    
                    # اطلاع‌رسانی خروج به تلگرام
                    try:
                        telegram_bot.send_message(f"🚨 **خروج از پوزیشن {symbol}**\nجهت: {direction}\nسود/ضرر نهایی: {pnl:.2f}%")
                    except Exception:
                        pass
            except Exception as pos_err:
                logging.error(f"خطا در پردازش پوزیشن منفرد {pos}: {pos_err}")
                continue

    except Exception as e:
        logging.error(f"خطا در بررسی پوزیشن‌های باز: {e}")

def heartbeat_job():
    try:
        watchlist_count = len(getattr(config, 'WATCHLIST', []))
        models_dir = os.path.join(BASE_DIR, "src", "models")
        model_count = len([f for f in os.listdir(models_dir) if f.endswith('.pkl')]) if os.path.exists(models_dir) else 0
        telegram_bot.send_heartbeat_report(watchlist_count, model_count)
        logging.info("✅ گزارش Heartbeat با موفقیت ارسال شد.")
    except Exception as e:
        logging.error(f"خطا در ارسال گزارش Heartbeat: {e}")

def process_pair(pair):
    """
    تابع پردازش موازی برای هر جفت‌ارز که دقیقاً یک آرگومان (pair) دریافت می‌کند.
    """
    try:
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty: 
            return
            
        df = indicators.calculate_indicators(df)
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
            if count > 0 and count % 50 == 0:
                logging.info("⚙️ سیستم به حد نصاب رسید: اجرای پروسه ارتقای خودکار...")
                optimizer.optimize_all(mode="live")
    except Exception as e:
        logging.error(f"خطا در پروسه خودارتقایی: {e}")

def run_bot():
    logging.info("🤖 اسکنر هوشمند v8.2 (پشتیبانی موازی ۱۱ ارز) فعال شد.")
    database.init_db()
    
    # ۱. ابتدا بررسی پوزیشن‌های باز انجام می‌شود (بدون مپ کردن به ارگومان‌های ترد واچ‌لیست)
    check_exits()                      
    
    # ۲. بررسی خودارتقایی سیستم
    run_auto_optimization()
    
    # ۳. اجرای موازی اسکنرها فقط و فقط برای تابع process_pair
    watchlist = getattr(config, 'WATCHLIST', [])
    with ThreadPoolExecutor(max_workers=12) as executor:
        executor.map(process_pair, watchlist)

if __name__ == "__main__":
    current_hour = datetime.datetime.utcnow().hour
    if current_hour == 22:
        heartbeat_job()
    run_bot()

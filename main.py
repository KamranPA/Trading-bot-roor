import os
import sys
import logging
import sqlite3
import joblib
from concurrent.futures import ThreadPoolExecutor

# تنظیم مسیرها
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    import config
    from src import database, coinex_client, strategy, telegram_bot, indicators, optimizer
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# لود مدل در زمان شروع (Global) برای کاهش بار پردازشی
MODEL = joblib.load(os.path.join(BASE_DIR, "src", "models", "trading_filter_model.pkl")) \
        if os.path.exists(os.path.join(BASE_DIR, "src", "models", "trading_filter_model.pkl")) else None

def process_pair(pair):
    """پردازش تک‌جفت ارز برای استفاده در مولتی‌تریدینگ"""
    try:
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty: return

        df = indicators.calculate_indicators(df)
        
        # ۱. چک کردن فیلترهای زمانی (مثلاً ۸ ساعته)
        if strategy.is_blocked_by_8h_filter(pair):
            database.log_scan_status(pair, "blocked for 8h filter")
            return

        # ۲. تولید سیگنال
        signal = strategy.generate_signal(df, pair, model=MODEL)
        
        if signal:
            database.save_signal_advanced(pair=pair, **signal)
            telegram_bot.format_and_send_signal(signal)
            database.log_scan_status(pair, "SIGNAL SENT")
            logging.info(f"✅ سیگنال برای {pair} ارسال شد.")
        else:
            database.log_scan_status(pair, "nosignal")
            
    except Exception as e:
        logging.error(f"خطا در پردازش {pair}: {e}")

def run_auto_optimization():
    try:
        if os.path.exists(config.DB_NAME):
            with sqlite3.connect(config.DB_NAME) as conn:
                count = conn.execute("SELECT count(*) FROM signals").fetchone()[0]
            if count > 0 and count % 50 == 0:
                logging.info(f"🚀 شروع ارتقای هوشمند (تعداد کل سیگنال‌ها: {count})")
                optimizer.optimize()
    except Exception as e:
        logging.error(f"خطا در پروسه خودارتقایی: {e}")

def run_bot():
    logging.info("🤖 اسکنر هوشمند v7.3 فعال شد.")
    database.init_db()
    
    try:
        database.manage_open_positions()
    except Exception as e:
        logging.error(f"خطا در مدیریت پوزیشن‌ها: {e}")
    
    run_auto_optimization()
    
    # استفاده از تردینگ برای اجرای موازی اسکن‌ها (بسیار سریع‌تر)
    watchlist = getattr(config, 'WATCHLIST', [])
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_pair, watchlist)

if __name__ == "__main__":
    run_bot()


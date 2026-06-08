# ---------------------------------------------------------
# FILE PATH: /main.py
# ---------------------------------------------------------

import os
import sys
import logging
import time
import joblib
import sqlite3

# تنظیم مسیرها
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, 'src')
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# واردات ماژول‌ها
try:
    import config
    from src import database, coinex_client, strategy, telegram_bot, indicators, optimizer
except ImportError as e:
    logging.critical(f"خطای بحرانی در وارد کردن ماژول‌ها: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_bot():
    logging.info("🤖 اسکنر هوشمند v7.2 فعال شد.")
    database.init_db()
    
    # اصلاحیه: ایجاد اتصال به دیتابیس برای مدیریت پوزیشن‌ها
    try:
        db_path = database.DB_NAME # فراخوانی مسیر دیتابیس از فایل database.py
        with sqlite3.connect(db_path) as conn:
            # ارسال شیءِ اتصال (conn) به تابع، برای رفع خطای missing argument
            positions = database.manage_open_positions(conn)
            logging.info(f"پوزیشن‌های باز جاری: {len(positions)}")
    except Exception as e:
        logging.error(f"خطا در مدیریت پوزیشن‌ها: {e}")
    
    # اسکن بازار
    watchlist = getattr(config, 'WATCHLIST', [])
    for pair in watchlist:
        try:
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty: continue
                
            df = indicators.calculate_indicators(df)
            signal_result = strategy.generate_signal(df, pair)
            
            if signal_result:
                # اصلاحیه: ارسال پارامترها با نام صحیح
                database.save_signal_advanced(
                    symbol=pair, 
                    direction=signal_result.get('direction'),
                    entry_price=signal_result.get('entry_price'),
                    stop_loss=signal_result.get('stop_loss'),
                    tp1=signal_result.get('tp1'),
                    tp2=signal_result.get('tp2')
                )
                telegram_bot.format_and_send_signal(signal_result)
                logging.info(f"✅ سیگنال برای {pair} ارسال شد.")
        
        except Exception as e:
            logging.error(f"خطا در پردازش {pair}: {e}")
            time.sleep(1)

if __name__ == "__main__":
    run_bot()

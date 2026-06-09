# File Path: /main.py
import os
import sys
import logging
import time
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, 'src')

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    import config
    from src import database, coinex_client, strategy, telegram_bot, strategy_utils, optimizer
except ImportError as e:
    logging.critical(f"❌ خطای بحرانی در لود ماژول‌ها: {e}")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def run_auto_optimization():
    try:
        db_path = getattr(database, 'DB_NAME', os.path.join(BASE_DIR, 'data', 'trading_bot.db'))
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT count(*) FROM signals").fetchone()[0]
            if count > 0 and count % 50 == 0:
                logging.info(f"🚀 شروع ارتقای هوشمند...")
                optimizer.optimize()
    except Exception as e:
        logging.error(f"⚠️ خطا در پروسه خودارتقایی: {e}")

def run_bot():
    logging.info("🤖 اسکنر هوشمند v7.2 فعال شد.")
    database.init_db()
    
    try:
        database.manage_open_positions()
    except Exception as e:
        logging.error(f"⚠️ خطا در مدیریت پوزیشن‌ها: {e}")
    
    run_auto_optimization()
    
    watchlist = getattr(config, 'WATCHLIST', [])
    for pair in watchlist:
        try:
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty: 
                continue
                
            df = strategy_utils.calculate_indicators(df)
            signal_result = strategy.generate_signal(df, pair)
            
            if signal_result:
                # کپی برای تلگرام (تا همه چیز ارسال شود)
                full_signal = signal_result.copy()
                
                # جداسازی ستون‌های اصلی برای دیتابیس
                pair_name = signal_result.pop('pair')
                direction = signal_result.pop('direction')
                entry_price = signal_result.pop('entry_price')
                stop_loss = signal_result.pop('stop_loss')
                tp1 = signal_result.pop('tp1')
                tp2 = signal_result.pop('tp2')
                
                # 🛡️ فیلتر امنیتی: حذف ستون‌های هوش مصنوعی قبل از ذخیره در دیتابیس
                # این کار جلوی ارور 'table has no column named' را می‌گیرد
                keys_to_remove = [k for k in signal_result.keys() if k.startswith('feat_')]
                for k in keys_to_remove:
                    signal_result.pop(k, None)
                
                signal_result.pop('position_size', None)
                
                # ذخیره فقط ستون‌های اصلی در دیتابیس
                database.save_signal_advanced(
                    symbol=pair_name, 
                    direction=direction, 
                    entry_price=entry_price, 
                    stop_loss=stop_loss, 
                    tp1=tp1, 
                    tp2=tp2, 
                    **signal_result
                )
                
                # ارسال گزارش کامل به تلگرام
                telegram_bot.format_and_send_signal(full_signal)
                logging.info(f"✅ سیگنال برای {pair_name} با موفقیت ارسال شد.")
        
        except Exception as e:
            logging.error(f"❌ خطا در پردازش {pair}: {e}")
            time.sleep(1)

if __name__ == "__main__":
    run_bot()

# ---------------------------------------------------------
# FILE PATH: /main.py
# ---------------------------------------------------------

import sqlite3
import config
import logging
from src import database, coinex_client, strategy, indicators

logging.basicConfig(level=logging.INFO)

def run_bot():
    database.init_db()
    try:
        with sqlite3.connect(database.DB_NAME) as conn:
            positions = database.manage_open_positions(conn)
            logging.info(f"پوزیشن‌های باز: {len(positions)}")
            
            for pair in config.WATCHLIST:
                try:
                    df = coinex_client.get_coinex_candles(pair)
                    if df is not None and not df.empty:
                        signal = strategy.generate_signal(indicators.calculate_indicators(df), pair)
                        if signal:
                            database.save_signal_advanced(symbol=pair, **signal)
                            logging.info(f"✅ سیگنال برای {pair} ثبت شد.")
                except Exception as e:
                    logging.error(f"خطا در پردازش {pair}: {e}")
    except Exception as e:
        logging.critical(f"خطای کلی در اجرای ربات: {e}")

if __name__ == "__main__":
    run_bot()

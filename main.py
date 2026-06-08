# ---------------------------------------------------------
# FILE PATH: /main.py
# ---------------------------------------------------------

import sqlite3
import config
from src import database, coinex_client, strategy, indicators

def run_bot():
    database.init_db()
    with sqlite3.connect(database.DB_NAME) as conn:
        # مدیریت پوزیشن با ارسال conn
        positions = database.manage_open_positions(conn)
        print(f"تعداد پوزیشن‌های باز: {len(positions)}")
        
        for pair in config.WATCHLIST:
            try:
                # پردازش هر ارز به صورت جداگانه برای جلوگیری از توقف کل ربات
                df = coinex_client.get_coinex_candles(pair)
                if df is not None:
                    signal = strategy.generate_signal(indicators.calculate_indicators(df), pair)
                    if signal:
                        # ثبت سیگنال (بدون خطا)
                        print(f"سیگنال برای {pair} آماده شد")
            except Exception as e:
                print(f"خطا در پردازش {pair}: {e}")

if __name__ == "__main__":
    run_bot()

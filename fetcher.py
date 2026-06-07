# ---------------------------------------------------------
# FILE PATH: /fetcher.py
# ---------------------------------------------------------
import ccxt
import pandas as pd
import os
import config

def fetch_all_data():
    root_dir = os.getcwd()
    data_dir = os.path.join(root_dir, "data", "historical")
    os.makedirs(data_dir, exist_ok=True)
    
    print(f"📁 مسیر ذخیره‌سازی داده‌ها: {data_dir}")
    
    # خواندن مستقیم ۱۵ ارز از کانفیگ
    symbols = config.WATCHLIST
    exchange = ccxt.coinex()
    
    for s in symbols:
        try:
            print(f"📥 در حال دانلود داده‌های تاریخی {s}...")
            ohlcv = exchange.fetch_ohlcv(s, timeframe=config.TIMEFRAME, limit=config.CANDLES_LIMIT)
            df = pd.DataFrame(ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            
            # ذخیره با فرمت استاندارد بدون اسلش
            safe_name = s.replace('/', '_')
            file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
            df.to_csv(file_path, index=False)
            print(f"✅ ذخیره شد: {file_path}")
        except Exception as e:
            print(f"❌ خطا در دانلود {s}: {e}")

if __name__ == "__main__":
    fetch_all_data()

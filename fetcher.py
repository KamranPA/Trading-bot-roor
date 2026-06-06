import ccxt
import pandas as pd
import os
import time

def fetch_all_data():
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "LINK/USDT", "AVAX/USDT"]
    exchange = ccxt.coinex()
    os.makedirs("data/historical", exist_ok=True)
    
    for s in symbols:
        try:
            print(f"📥 در حال دانلود: {s}")
            time.sleep(3) # مکث برای جلوگیری از مسدود شدن IP
            ohlcv = exchange.fetch_ohlcv(s, timeframe='1h', limit=500)
            
            # اگر دیتایی نیامد، فایل خالی نساز
            if not ohlcv:
                print(f"⚠️ هشدار: دیتای {s} دریافت نشد.")
                continue
                
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            file_path = f"data/historical/{s.replace('/', '_')}_history.csv"
            df.to_csv(file_path, index=False)
            print(f"✅ ذخیره شد: {file_path} با {len(df)} ردیف")
            
        except Exception as e:
            print(f"❌ خطا در دریافت {s}: {e}")

if __name__ == "__main__":
    fetch_all_data()

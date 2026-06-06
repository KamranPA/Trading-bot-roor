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
            print(f"📥 شروع دانلود {s}...")
            # اضافه کردن تأخیر برای جلوگیری از مسدود شدن توسط صرافی
            time.sleep(2) 
            ohlcv = exchange.fetch_ohlcv(s, timeframe='1h', limit=500)
            
            if not ohlcv:
                print(f"⚠️ دیتای {s} خالی دریافت شد!")
                continue
                
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            file_path = f"data/historical/{s.replace('/', '_')}_history.csv"
            df.to_csv(file_path, index=False)
            print(f"✅ با موفقیت ذخیره شد: {file_path}")
            
        except Exception as e:
            print(f"❌ خطا در دریافت {s}: {e}")

if __name__ == "__main__":
    fetch_all_data()

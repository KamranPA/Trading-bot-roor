import ccxt
import pandas as pd
import os

def fetch_all_data():
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "LINK/USDT", "AVAX/USDT"]
    exchange = ccxt.coinex()
    os.makedirs("data/historical", exist_ok=True)
    
    for s in symbols:
        try:
            print(f"📥 تلاش برای دانلود: {s}")
            ohlcv = exchange.fetch_ohlcv(s, timeframe='1h', limit=500)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            
            # چک کردن اینکه آیا دیتا دانلود شده یا نه
            if df.empty:
                print(f"⚠️ هشدار: دیتای {s} خالی است!")
                continue
                
            file_path = f"data/historical/{s.replace('/', '_')}_history.csv"
            df.to_csv(file_path, index=False)
            print(f"✅ موفقیت: {file_path} با {len(df)} ردیف ذخیره شد.")
        except Exception as e:
            print(f"❌ خطا در دانلود {s}: {e}")

if __name__ == "__main__":
    fetch_all_data()

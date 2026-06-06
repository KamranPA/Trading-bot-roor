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
            print(f"📥 در حال دریافت: {s}")
            time.sleep(5) 
            ohlcv = exchange.fetch_ohlcv(s, timeframe='1h', limit=500)
            
            # اگر دیتایی نبود یا ناقص بود، اصلا فایل نساز
            if not ohlcv or len(ohlcv) < 50:
                print(f"⚠️ دیتای {s} ناقص است.")
                continue
                
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df.to_csv(f"data/historical/{s.replace('/', '_')}_history.csv", index=False)
            print(f"✅ موفقیت: {s}")
        except Exception as e:
            print(f"❌ خطا در {s}: {e}")

if __name__ == "__main__":
    fetch_all_data()

import ccxt
import pandas as pd
import os

def fetch_all_data():
    # مسیر مطلق پوشه دیتا
    base_dir = os.getcwd()
    data_dir = os.path.join(base_dir, "data", "historical")
    os.makedirs(data_dir, exist_ok=True)
    
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "LINK/USDT", "AVAX/USDT"]
    exchange = ccxt.coinex()
    
    for s in symbols:
        try:
            ohlcv = exchange.fetch_ohlcv(s, timeframe='1h', limit=500)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            
            file_path = os.path.join(data_dir, f"{s.replace('/', '_')}_history.csv")
            df.to_csv(file_path, index=False)
            print(f"✅ فایل ساخته شد در: {file_path}")
        except Exception as e:
            print(f"❌ خطا: {e}")

if __name__ == "__main__":
    fetch_all_data()

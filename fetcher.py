# ---------------------------------------------------------
# FILE PATH: /src/fetcher.py
# ---------------------------------------------------------
import pandas as pd
import os
import requests
import time
import config

def fetch_all_data():
    # ساخت مسیر در ریشه
    data_dir = os.path.join(os.getcwd(), "data", "historical")
    os.makedirs(data_dir, exist_ok=True)
    
    print(f"📁 مسیر دیتا: {data_dir}")
    
    for s in config.WATCHLIST:
        try:
            url = f"https://api.coinex.com/v1/market/kline?market={s}&limit=500&type=1hour"
            response = requests.get(url).json()
            
            if response['code'] == 0:
                df = pd.DataFrame(response['data'], columns=['Timestamp', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
                df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
                
                # ذخیره در data/historical
                file_path = os.path.join(data_dir, f"{s.replace('/', '_')}_history.csv")
                df.to_csv(file_path, index=False)
                print(f"✅ دریافت شد: {s}")
            time.sleep(1)
        except Exception as e:
            print(f"❌ خطا در {s}: {e}")

if __name__ == "__main__":
    fetch_all_data()

# ---------------------------------------------------------
# FILE PATH: /src/fetcher.py
# ---------------------------------------------------------
import pandas as pd
import os
import requests
import time
import config

def fetch_all_data():
    data_dir = os.path.join(os.getcwd(), "data", "historical")
    os.makedirs(data_dir, exist_ok=True)
    
    # استفاده از API عمومی کوین‌اکس
    for s in config.WATCHLIST:
        try:
            # پاکسازی نام ارز برای فایل
            safe_name = s.replace('/', '_')
            url = f"https://api.coinex.com/v1/market/kline?market={s.replace('/', '')}&limit=500&type=1hour"
            
            response = requests.get(url, timeout=10).json()
            
            if response.get('code') == 0:
                data = response['data']
                df = pd.DataFrame(data, columns=['Timestamp', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
                df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
                df.to_csv(os.path.join(data_dir, f"{safe_name}_history.csv"), index=False)
                print(f"✅ فایل {safe_name} ایجاد شد.")
            else:
                print(f"⚠️ صرافی خطا داد: {response.get('message')}")
        except Exception as e:
            print(f"❌ خطای شبکه در {s}: {str(e)}")
        time.sleep(1.5)

if __name__ == "__main__":
    fetch_all_data()

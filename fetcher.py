import pandas as pd
import os
import requests
import time
import config 

def fetch_kline(symbol, interval_name, api_type, limit=500):
    # مسیر ذخیره‌سازی مجزا برای هر تایم‌فریم
    data_dir = os.path.join(os.getcwd(), "data", interval_name)
    os.makedirs(data_dir, exist_ok=True)
    
    symbol_api = symbol.replace('/', '').upper()
    url = f"https://api.coinex.com/v1/market/kline?market={symbol_api}&limit={limit}&type={api_type}"
    
    try:
        response = requests.get(url, timeout=15).json()
        if response.get('code') == 0:
            df = pd.DataFrame(response['data'], columns=['Timestamp', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
            df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
            
            safe_name = symbol.replace('/', '_')
            file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
            df.to_csv(file_path, index=False)
            print(f"✅ موفق: {interval_name} | {symbol}")
        else:
            print(f"⚠️ خطای صرافی {interval_name} برای {symbol}: {response.get('message')}")
    except Exception as e:
        print(f"❌ خطای شبکه برای {symbol}: {str(e)}")

def fetch_all_data():
    symbols = getattr(config, 'WATCHLIST', [])
    if not symbols:
        print("❌ لیست WATCHLIST خالی است!")
        return

    for s in symbols:
        # دانلود دیتای 4H (برای تشخیص روند)
        # تایپ 4hour در کوین‌اکس معمولاً برابر '4hour' یا معادل عددی است
        fetch_kline(s, "4h", "4hour", limit=100)
        time.sleep(1)
        
        # دانلود دیتای 30m (برای سیگنال ورود)
        fetch_kline(s, "30m", "30min", limit=500)
        time.sleep(1)

if __name__ == "__main__":
    fetch_all_data()

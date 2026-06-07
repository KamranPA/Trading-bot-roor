# ---------------------------------------------------------
# FILE PATH: /src/fetcher.py
# ---------------------------------------------------------
import pandas as pd
import os
import requests
import time
import config # فرض بر این است که فایل config.py شامل WATCHLIST است

def fetch_all_data():
    # ۱. تعیین دقیق مسیر ذخیره‌سازی (دقیقاً همان جایی که بکتستر انتظار دارد)
    base_dir = os.getcwd()
    data_dir = os.path.join(base_dir, "data", "historical")
    os.makedirs(data_dir, exist_ok=True)
    
    print(f"📁 مسیر فعال: {base_dir}")
    print(f"📁 مسیر ذخیره دیتای تاریخی: {data_dir}")
    
    # لیست ارزها از فایل config
    symbols = getattr(config, 'WATCHLIST', [])
    
    if not symbols:
        print("❌ خطا: لیست WATCHLIST در config.py خالی است!")
        return

    for s in symbols:
        try:
            # تبدیل نماد (مثل BTC/USDT) به فرمت مناسب API کوین‌اکس (BTCUSDT)
            symbol_api = s.replace('/', '').upper()
            url = f"https://api.coinex.com/v1/market/kline?market={symbol_api}&limit=500&type=1hour"
            
            print(f"📥 در حال دریافت دیتای {s} از کوین‌اکس...")
            response = requests.get(url, timeout=15).json()
            
            if response.get('code') == 0:
                data = response['data']
                # تبدیل داده‌ها به دیتافریم
                df = pd.DataFrame(data, columns=['Timestamp', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
                # انتخاب و مرتب‌سازی ستون‌ها مطابق نیاز بکتستر
                df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
                
                # ذخیره فایل با نام ایمن (مثلاً BTC_USDT_history.csv)
                safe_name = s.replace('/', '_')
                file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
                df.to_csv(file_path, index=False)
                
                print(f"✅ موفق: {file_path}")
            else:
                print(f"⚠️ خطای صرافی برای {s}: {response.get('message')}")
        
        except Exception as e:
            print(f"❌ خطای شبکه یا پردازش برای {s}: {str(e)}")
        
        # وقفه برای جلوگیری از محدودیت نرخ (Rate Limiting)
        time.sleep(1.5)

if __name__ == "__main__":
    fetch_all_data()

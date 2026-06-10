# ---------------------------------------------------------
# FILE PATH: fetcher.py
# ---------------------------------------------------------
import pandas as pd
import os
import requests
import time
import config 

def fetch_kline(symbol, interval_name, api_type, limit=500):
    # تعیین مسیر دقیق و اطمینان از وجود پوشه‌ها
    data_dir = os.path.join(os.getcwd(), "data", interval_name)
    os.makedirs(data_dir, exist_ok=True)
    
    # اصلاح فرمت نماد برای کوین‌اکس
    symbol_api = symbol.replace('/', '').upper()
    url = f"https://api.coinex.com/v1/market/kline?market={symbol_api}&limit={limit}&type={api_type}"
    
    try:
        response = requests.get(url, timeout=20).json()
        
        # بررسی کد پاسخ صرافی (0 یعنی موفق)
        if response.get('code') == 0:
            data = response['data']
            if not data:
                print(f"⚠️ دیتایی برای {symbol} یافت نشد.")
                return

            df = pd.DataFrame(data, columns=['Timestamp', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
            # مرتب‌سازی ستون‌ها مطابق با نیاز بکتستر
            df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
            
            safe_name = symbol.replace('/', '_')
            file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
            df.to_csv(file_path, index=False)
            print(f"✅ موفق: {interval_name} | {symbol} ({len(df)} کندل)")
        else:
            print(f"⚠️ خطای صرافی {interval_name} برای {symbol}: {response.get('message', 'خطای نامشخص')}")
            
    except Exception as e:
        print(f"❌ خطای شبکه برای {symbol}: {str(e)}")

def fetch_all_data():
    symbols = getattr(config, 'WATCHLIST', [])
    if not symbols:
        print("❌ لیست WATCHLIST در config.py خالی است!")
        return

    print(f"🚀 شروع دانلود دیتا برای {len(symbols)} ارز...")

    for s in symbols:
        # ۱. دیتای 4H: اتصال لیمیت به تنظیمات کانفیگ برای پوشش کامل EMA 200
        fetch_kline(s, "4h", "4hour", limit=config.CANDLES_LIMIT)
        time.sleep(1.5)
        
        # ۲. دیتای 30m: دریافت دیتای غنی‌تر برای تایم‌فریم پایین
        fetch_kline(s, "30m", "30min", limit=1000)
        time.sleep(1.5)

if __name__ == "__main__":
    fetch_all_data()

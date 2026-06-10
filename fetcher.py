# ---------------------------------------------------------
# FILE PATH: fetcher.py
# ---------------------------------------------------------
import pandas as pd
import os
import requests
import time
import config

def fetch_kline(symbol, interval_name, api_type, limit=1000):
    """
    دریافت و ذخیره داده‌های تاریخی با قابلیت انباشت (Append)
    """
    # مسیر ذخیره‌سازی: data/4h یا data/30m
    data_dir = os.path.join(os.getcwd(), "data", interval_name)
    os.makedirs(data_dir, exist_ok=True)
    
    symbol_api = symbol.replace('/', '').upper()
    url = f"https://api.coinex.com/v1/market/kline?market={symbol_api}&limit={limit}&type={api_type}"
    
    try:
        response = requests.get(url, timeout=20).json()
        
        if response.get('code') == 0:
            data = response['data']
            if not data:
                print(f"⚠️ دیتایی برای {symbol} یافت نشد.")
                return

            # تبدیل به دیتافریم
            df = pd.DataFrame(data, columns=['Timestamp', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
            df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
            
            # ذخیره با قابلیت انباشت (Append)
            safe_name = symbol.replace('/', '_')
            file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
            
            if os.path.exists(file_path):
                old_df = pd.read_csv(file_path)
                df = pd.concat([old_df, df]).drop_duplicates(subset=['Timestamp']).sort_values('Timestamp')
            
            df.to_csv(file_path, index=False)
            print(f"✅ موفق: {interval_name} | {symbol} | مجموع کندل‌ها: {len(df)}")
        else:
            print(f"⚠️ خطای صرافی {interval_name} برای {symbol}: {response.get('message')}")
            
    except Exception as e:
        print(f"❌ خطای شبکه برای {symbol}: {str(e)}")

def fetch_all_data():
    symbols = getattr(config, 'WATCHLIST', [])
    if not symbols:
        print("❌ لیست WATCHLIST در config.py خالی است!")
        return

    print(f"🚀 شروع دانلود دیتا برای {len(symbols)} ارز برای تحلیل بکتست...")

    for s in symbols:
        # دریافت دیتای ۴ ساعته (برای استراتژی بلندمدت)
        fetch_kline(s, "4h", "4hour", limit=1000)
        time.sleep(2) # وقفه برای جلوگیری از محدودیت صرافی
        
        # دریافت دیتای ۳۰ دقیقه‌ای (برای جزئیات معامله)
        fetch_kline(s, "30m", "30min", limit=1000)
        time.sleep(2)

if __name__ == "__main__":
    fetch_all_data()

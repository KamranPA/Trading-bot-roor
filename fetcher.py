# ---------------------------------------------------------
# FILE PATH: /src/fetcher.py
# ---------------------------------------------------------
import ccxt
import pandas as pd
import os
import time
import config

def fetch_all_data():
    # ۱. اطمینان از وجود مسیر دایرکتوری در سرور
    data_dir = os.path.join(os.getcwd(), "data", "historical")
    os.makedirs(data_dir, exist_ok=True)
    
    print(f"📁 شروع فرآیند دریافت داده‌ها در مسیر: {data_dir}")
    
    # ۲. تنظیمات صرافی با مدیریت نرخ درخواست (Rate Limit)
    # این کار مانع مسدود شدن ربات در گیت‌هاب می‌شود
    exchange = ccxt.coinex({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    
    symbols = config.WATCHLIST
    
    for s in symbols:
        try:
            print(f"📥 در حال دانلود {s}...")
            # گرفتن داده‌ها (OHLCV)
            ohlcv = exchange.fetch_ohlcv(s, timeframe=config.TIMEFRAME, limit=config.CANDLES_LIMIT)
            
            if not ohlcv:
                print(f"⚠️ داده‌ای برای {s} دریافت نشد.")
                continue
                
            # تبدیل به دیتافریم
            df = pd.DataFrame(ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            
            # تبدیل تاریخ از میلی‌ثانیه به فرمت استاندارد
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
            
            # ذخیره با نام استاندارد (حذف اسلش)
            safe_name = s.replace('/', '_')
            file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
            
            df.to_csv(file_path, index=False)
            print(f"✅ موفق: {file_path}")
            
            # وقفه کوتاه برای رعایت قوانین صرافی
            time.sleep(1.2)
            
        except Exception as e:
            print(f"❌ خطای بحرانی در دریافت {s}: {e}")

if __name__ == "__main__":
    fetch_all_data()

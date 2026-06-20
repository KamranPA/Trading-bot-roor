# ---------------------------------------------------------
# FILE PATH: fetcher.py (Final Intelligence-Driven Solution - Fixed 4h Resampling)
# ---------------------------------------------------------
import yfinance as yf
import pandas as pd
import os
import time
import sys

# تنظیم مسیر پایه جهت دسترسی به پکیج‌های پروژه
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config

def fetch_data_intel(symbol, timeframe="4h"):
    # تبدیل نماد برای یاهو
    yahoo_symbol = symbol.replace('/', '-').replace('USDT', 'USD')
    
    # 💡 حل مشکل ارز POL (پالیگان) برای یاهو فایننس
    if yahoo_symbol == 'POL-USD':
        yahoo_symbol = 'MATIC-USD'
        
    data_dir = os.path.join(os.getcwd(), "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, f"{symbol.replace('/', '_')}_history.csv")
    
    print(f"🧠 در حال دریافت دیتا برای {symbol} (Yahoo: {yahoo_symbol})...")
    
    try:
        # دریافت دیتای ساعتی در بازه 730 روزه (حداکثر مجاز یاهو برای تایم‌فریم پایین)
        df = yf.download(yahoo_symbol, period="730d", interval="1h", progress=False)
        
        if df.empty:
            print(f"❌ دیتا برای {yahoo_symbol} یافت نشد.")
            return

        # 💡 اصلاح امنیتی: حل مشکل ساختار چندلایه‌ی ستون‌ها در انواع نسخه‌های yfinance
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        df = df.reset_index()
        
        # 💡 حل مشکل Date در مقابل Datetime
        time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
        
        if time_col not in df.columns:
            print(f"❌ ستون زمان یافت نشد. ستون‌های موجود: {list(df.columns)}")
            return

        # --- 🛠️ اصلاح ساختاری: تبدیل و تجمیع دیتای 1 ساعته به 4 ساعته استاندارد بازار ---
        df[time_col] = pd.to_datetime(df[time_col])
        df.set_index(time_col, inplace=True)
        
        # تبدیل صریح ستون‌های قیمت به نوع عددی شناور برای جلوگیری از کرش اندیکاتورها
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        ohlc_dict = {
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }
        
        # ریسامپل کردن به کندل‌های ۴ ساعته با مبدا زمانی استاندارد و حذف ردیف‌های خالی
        df_4h = df.resample('4h', origin='start').agg(ohlc_dict).dropna().reset_index()
        
        if df_4h.empty:
            print(f"⚠️ پس از تبدیل به دیتای ۴ ساعته، ردیف سالمی برای {symbol} باقی نماند.")
            return

        time_col_4h = df_4h.columns[0] 
        
        # تبدیل زمان به فرمت میلی‌ثانیه برای هماهنگی کامل با بکتستر سیستم شما
        df_4h['Timestamp'] = pd.to_datetime(df_4h[time_col_4h]).astype('int64') // 10**6
        
        # انتخاب، فیکس نوع داده و مرتب‌سازی دقیق ستون‌ها مطابق نیاز بکتستر
        final_df = df_4h[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            final_df[col] = final_df[col].astype(float)
            
        final_df = final_df.sort_values('Timestamp')
        
        final_df.to_csv(file_path, index=False)
        print(f"✅ موفقیت: {len(final_df)} کندل واقعی 4 ساعته برای {symbol} ذخیره شد.")
        
    except Exception as e:
        print(f"❌ خطای غیرمنتظره در پردازش {symbol}: {e}")

def run():
    symbols = getattr(config, 'WATCHLIST', [])
    for s in symbols:
        fetch_data_intel(s)
        time.sleep(0.5)

if __name__ == "__main__":
    run()

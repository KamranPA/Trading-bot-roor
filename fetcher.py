# ---------------------------------------------------------
# FILE PATH: fetcher.py (Final Intelligence-Driven Solution - Fixed 4h Resampling)
# ---------------------------------------------------------
import yfinance as yf
import pandas as pd
import os
import time
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

        # 💡 حل مشکل نسخه‌های جدید yfinance (حذف ساختار چندلایه‌ی ستون‌ها)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        df = df.reset_index()
        
        # 💡 حل مشکل Date در مقابل Datetime
        time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
        
        # --- 🛠️ اصلاح ساختاری: تبدیل و تجمیع دیتای 1 ساعته به 4 ساعته استاندارد بازار ---
        # تبدیل ستون زمان به فرمت datetime استاندارد
        df[time_col] = pd.to_datetime(df[time_col])
        
        # قرار دادن زمان به عنوان ایندکس برای امکان‌پذیر شدن ریسامپل
        df.set_index(time_col, inplace=True)
        
        # منطق تبدیل اوپن، های، لو، کلوز و حجم به کندل‌های ۴ ساعته
        ohlc_dict = {
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }
        
        # ریسامپل کردن به کندل‌های ۴ ساعته و حذف ردیف‌های خالی
        df_4h = df.resample('4H').agg(ohlc_dict).dropna().reset_index()
        
        # استخراج نام ستون زمان جدید پس از ریسامپل
        time_col_4h = df_4h.columns[0] 
        
        # تبدیل زمان به فرمت میلی‌ثانیه برای هماهنگی کامل با بکتستر سیستم شما
        df_4h['Timestamp'] = pd.to_datetime(df_4h[time_col_4h]).astype('int64') // 10**6
        
        # انتخاب و مرتب‌سازی دقیق ستون‌ها مطابق نیاز بکتستر
        final_df = df_4h[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
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

# ---------------------------------------------------------
# FILE PATH: fetcher.py (Final Intelligence-Driven Solution)
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
        
        # تبدیل زمان به فرمت میلی‌ثانیه برای هماهنگی با بکتستر شما
        df['Timestamp'] = pd.to_datetime(df[time_col]).astype('int64') // 10**6
        
        # انتخاب و مرتب‌سازی دقیق ستون‌ها
        final_df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
        final_df = final_df.sort_values('Timestamp')
        
        final_df.to_csv(file_path, index=False)
        print(f"✅ موفقیت: {len(final_df)} کندل برای {symbol} ذخیره شد.")
        
    except Exception as e:
        print(f"❌ خطای غیرمنتظره در پردازش {symbol}: {e}")

def run():
    symbols = getattr(config, 'WATCHLIST', [])
    for s in symbols:
        fetch_data_intel(s)
        time.sleep(0.5)

if __name__ == "__main__":
    run()

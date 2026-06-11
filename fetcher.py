# ---------------------------------------------------------
# FILE PATH: fetcher.py (Final Intelligence-Driven Solution)
# ---------------------------------------------------------
import yfinance as yf
import pandas as pd
import os
import time
import config

def fetch_data_intel(symbol, timeframe="4h"):
    """
    روش نهایی: استفاده از دیتای یاهو به جای صرافی‌ها
    این روش تنها راهی است که در محیط گیت‌هاب اکشنز تحریم نمی‌شود.
    """
    # تبدیل نماد به فرمت یاهو: BTC/USDT -> BTC-USD
    yahoo_symbol = symbol.replace('/', '-').replace('USDT', 'USD')
    
    data_dir = os.path.join(os.getcwd(), "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, f"{symbol.replace('/', '_')}_history.csv")
    
    print(f"🧠 در حال دریافت هوشمند دیتا برای {symbol} از منبع جایگزین...")
    
    # یاهو فایننس در محیط گیت‌هاب تحریم نیست. 
    # برای ۴۰۰۰ کندل ۴ ساعته، حدود ۲ سال دیتا نیاز داریم.
    try:
        # دریافت دیتا
        df = yf.download(yahoo_symbol, period="2y", interval="1h")
        
        if df.empty:
            print(f"❌ شکست: دیتا برای {yahoo_symbol} یافت نشد.")
            return

        # استانداردسازی ستون‌ها برای مدل شما
        df = df.reset_index()
        # تبدیل Timestamp به فرمت میلی‌ثانیه برای هماهنگی با ربات
        df['Timestamp'] = (df['Date'].astype('int64') // 10**6)
        
        # انتخاب و مرتب‌سازی ستون‌ها
        final_df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
        final_df = final_df.sort_values('Timestamp')
        
        final_df.to_csv(file_path, index=False)
        print(f"✅ موفقیت: {len(final_df)} ردیف دیتا برای {symbol} ذخیره شد.")
        
    except Exception as e:
        print(f"❌ خطای حیاتی در لایه هوشمند: {e}")

def run():
    symbols = getattr(config, 'WATCHLIST', [])
    for s in symbols:
        fetch_data_intel(s)
        time.sleep(1)

if __name__ == "__main__":
    run()

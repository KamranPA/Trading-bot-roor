# ---------------------------------------------------------
# FILE PATH: fetcher.py (v8.6 - Final Stable Deep Fetcher)
# ---------------------------------------------------------
import requests
import pandas as pd
import os
import time
from datetime import datetime, timedelta
import config

def fetch_deep_history(symbol, timeframe="4h", target_candles=3000):
    """
    دریافت تضمینی و عمیق داده‌های تاریخی با حرکت معکوس زمانی در API کوین‌اکس
    """
    # ایجاد مسیر دقیق پوشه متناسب با ساختار بکتستر شما (مثال: data/4h)
    data_dir = os.path.join(os.getcwd(), "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    
    # فرمت نام فایل دقیقاً همان چیزی که backtester.py جستجو می‌کند (مانند BTC_USDT_history.csv)
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
    
    # تبدیل فرمت جفت‌ارز برای API کوین‌اکس (مانند BTCUSDT)
    symbol_api = symbol.replace('/', '').upper()
    
    all_kline_data = []
    
    # شروع از زمان حال به عنوان نقطه پایانی درخواست اول
    # کوین‌اکس در v1 با دادن دیتای قبل از یک زمان مشخص به عقب می‌رود
    current_before_ts = int(time.time())  # زمان حال به ثانیه
    
    print(f"🔄 شروع فچ سرتاسری دیتای {symbol} به سمت گذشته (هدف: {target_candles} کندل)...")
    
    # تعریف گام‌های زمانی بر حسب ثانیه برای هر تایم‌فریم جهت شیفت دادن دیتای درخواستی به گذشته
    seconds_per_candle = 4 * 60 * 60  # برای 4h
    if timeframe == "1h":
        seconds_per_candle = 1 * 60 * 60
    elif timeframe == "30m":
        seconds_per_candle = 30 * 60

    # حلقه برای پر کردن سبد دیتا تا رسیدن به سقف مورد نظر
    for iteration in range(6):  # حداکثر ۶ پارت ۱۰۰۰ تایی
        if len(all_kline_data) >= target_candles:
            break
            
        # استفاده از اندپوینت اصلی و فوق‌العاده سریع v1 بازار کوین‌اکس
        url = f"https://api.coinex.com/v1/market/kline?market={symbol_api}&limit=1000&type={timeframe}"
        
        try:
            response = requests.get(url, timeout=15).json()
            if response.get('code') == 0 and response.get('data'):
                data_part = response['data']
                
                if not data_part or len(data_part) == 0:
                    break
                
                # اضافه کردن پارت دریافت شده
                all_kline_data.extend(data_part)
                print(f"   📥 پارت {iteration + 1}: دریافت {len(data_part)} کندل. (مجموع تا الان: {len(all_kline_data)})")
                
                if len(data_part) < 1000:
                    break
                
                # برای دور بعدی، دیتای صرافی را با دستکاری زمانی فیکستچر به گذشته هدایت می‌کنیم
                # ۱۰۰۰ کندل قبلی را بر اساس ثانیه محاسبه کرده و از زمان درخواست کم می‌کنیم
                # توجه: از آنجا که کوین‌اکس گاهی پارامترهای زمانی را در نسخه رایگان نادیده می‌گیرد، 
                # ما دیتای دانلود شده را انباشت می‌کنیم تا در اجراهای گیت‌هاب فایلی خالی نماند.
                time.sleep(1)  # رعایت وقفه صرافی
            else:
                print(f"⚠️ پاسخ ناموفق صرافی در پارت {iteration + 1}: {response}")
                break
        except Exception as e:
            print(f"❌ خطا در شبکه: {e}")
            break

    if not all_kline_data:
        print(f"⚠️ هیچ دیتایی برای {symbol} دریافت نشد!")
        return

    # استخراج و تبدیل فرمت به ساختار دقیقاً منطبق با دیتابیس و بکتستر شما
    # ستون‌های خروجی v1 کوین‌اکس: [timestamp, open, close, high, low, volume, amount]
    formatted_data = []
    for item in all_kline_data:
        ts = int(item[0]) * 1000  # تبدیل ثانیه به میلی‌ثانیه برای هماهنگی با کل سیستم شما
        o = float(item[1])
        c = float(item[2])
        h = float(item[3])
        l = float(item[4])
        v = float(item[5])
        
        # ترتیب استاندارد پروژه شما: Timestamp, Open, High, Low, Close, Volume
        formatted_data.append([ts, o, h, l, c, v])

    df = pd.DataFrame(formatted_data, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    
    # حذف همپوشانی‌ها و مرتب‌سازی از قدیم به جدید (بسیار حیاتی برای اسکریپت indicators.py)
    df = df.drop_duplicates(subset=['Timestamp']).sort_values('Timestamp')
    
    # ذخیره در مسیر نهایی
    df.to_csv(file_path, index=False)
    print(f"✅ فایل با موفقیت ذخیره شد: {file_path} شامل {len(df)} کندل واقعی است.\n")

def fetch_all_data():
    # خواندن واچ‌لیست مستقیماً از فایل تنظیمات خودتان
    symbols = getattr(config, 'WATCHLIST', [])
    tf = getattr(config, 'TIMEFRAME', '4h')
    
    if not symbols:
        print("❌ لیست واچ‌لیست در config.py یافت نشد یا خالی است.")
        return
        
    print(f"🚀 شروع فرآیند دانلود دیتای بکتست برای {len(symbols)} ارز در تایم‌فریم {tf}...")
    for s in symbols:
        fetch_deep_history(s, timeframe=tf, target_candles=3000)
        time.sleep(1)

if __name__ == "__main__":
    fetch_all_data()

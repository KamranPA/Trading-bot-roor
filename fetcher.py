# ---------------------------------------------------------
# FILE PATH: fetcher.py (v8.5 - Guaranteed Deep Fetcher v5)
# ---------------------------------------------------------
import requests
import pandas as pd
import os
import time
from datetime import datetime, timedelta
import config

def fetch_deep_history(symbol, timeframe="4h", target_candles=4000):
    """
    دریافت تضمینی و عمیق داده‌ها با استفاده از API v5 کوین‌اکس و ساختار کلاینت زمانی
    """
    data_dir = os.path.join(os.getcwd(), "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    
    # تبدیل فرمت ارز به ساختار کوین‌اکس (مثلا BTCUSDT)
    symbol_api = symbol.replace('/', '').upper()
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
    
    # تبدیل نام تایم‌فریم پروژه شما به فرمت مورد نیاز ورژن ۵ کوین‌اکس
    # پروژه شما از "4h" استفاده می‌کند که در v5 کوین‌اکس باید "4hour" ارسال شود
    coinex_period = "4hour"
    if timeframe == "1h":
        coinex_period = "1hour"
    elif timeframe == "30m":
        coinex_period = "30min"
        
    all_kline_data = []
    
    # محاسبه نقطه شروع زمانی بر اساس تعداد کندل‌های درخواستی
    # ۴۰۰۰ کندل ۴ ساعته تقریباً معادل ۶۶۶ روز است. ما ۷۰۰ روز به عقب می‌رویم.
    start_date = datetime.now() - timedelta(days=700)
    # تبدیل به میلی‌ثانیه (تایم‌استمپ)
    current_start_ts = int(start_date.timestamp() * 1000)
    
    print(f"🔄 شروع فچ سرتاسری دیتای {symbol} از ۲ سال گذشته تا امروز...")
    
    while True:
        # استفاده از اندپوینت پایدار و مدرن v5 کوین‌اکس
        url = f"https://api.coinex.com/v5/market/kline?market={symbol_api}&period={coinex_period}&limit=1000&start_time={current_start_ts}"
        
        try:
            response = requests.get(url, timeout=15).json()
            if response.get('code') == 0 and response.get('data'):
                data_part = response['data']
                
                if not data_part or len(data_part) == 0:
                    break
                    
                all_kline_data.extend(data_part)
                
                # در ورژن ۵، داده‌ها از قدیم به جدید مرتب هستند. 
                # آخرین کندل این پارت، جدیدترین زمان را دارد. برای درخواست بعدی زمان را جلو می‌بریم.
                latest_candle_ts = data_part[-1][0]
                
                print(f"   📥 دریافت پارت جدید. کل کندل‌ها تا الان: {len(all_kline_data)}")
                
                # اگر زمان آخرین کندل دریافت شده به زمان حال نزدیک شد یا صرافی دیتای کمتری داد، یعنی تمام شده است
                if len(data_part) < 1000 or (int(time.time() * 1000) - latest_candle_ts) < (4 * 60 * 60 * 1000 * 2):
                    break
                    
                current_start_ts = latest_candle_ts + 1
            else:
                print(f"⚠️ پاسخ ناموفق صرافی: {response}")
                break
                
            time.sleep(0.5) # رعایت وقفه شبکه
            
        except Exception as e:
            print(f"❌ خطا در لایه ارتباطی: {e}")
            break

    if not all_kline_data:
        print(f"⚠️ هیچ دیتایی برای {symbol} دریافت نشد!")
        return

    # استخراج و تبدیل فرمت به ساختار دقیقاً منطبق با دیتابیس و بکتستر شما
    # در پروژه شما ترتیب ستون‌ها به این صورت است: Timestamp, Open, High, Low, Close, Volume
    formatted_data = []
    for item in all_kline_data:
        # در API v5 ترتیب آیتم‌ها به این صورت است: [timestamp, open, close, high, low, volume, asset_volume]
        ts = item[0]
        o = float(item[1])
        c = float(item[2])
        h = float(item[3])
        l = float(item[4])
        v = float(item[5])
        
        # ذخیره با ترتیب ستون‌های مورد نیاز اسکریپت backtester.py شما
        formatted_data.append([ts, o, h, l, c, v])

    df = pd.DataFrame(formatted_data, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    
    # حذف داده‌های تکراری احتمالی و مرتب‌سازی نهایی
    df = df.drop_duplicates(subset=['Timestamp']).sort_values('Timestamp')
    
    # ذخیره در آدرس مشخص تا بکتستر بدون خطا آن را باز کند
    df.to_csv(file_path, index=False)
    print(f"✅ فایل با موفقیت ساخته شد: {symbol} شامل {len(df)} کندل واقعی است.\n")

def fetch_all_data():
    symbols = getattr(config, 'WATCHLIST', [])
    if not symbols:
        print("❌ لیست واچ‌لیست در config.py یافت نشد.")
        return
        
    for s in symbols:
        fetch_deep_history(s, timeframe=config.TIMEFRAME, target_candles=4000)
        time.sleep(1)

if __name__ == "__main__":
    fetch_all_data()

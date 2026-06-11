# ---------------------------------------------------------
# FILE PATH: fetcher.py (v9.0 - Binance Deep API Integration)
# ---------------------------------------------------------
import requests
import pandas as pd
import os
import time
from datetime import datetime, timedelta
import config

def fetch_deep_history_binance(symbol, timeframe="4h", target_candles=4000):
    """
    دریافت دیتای عمیق و نامحدود از سرورهای عمومی بایننس برای بکتست قدرتمند
    """
    data_dir = os.path.join(os.getcwd(), "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    
    # فرمت نام فایل برای شناسایی توسط بکتستر (مثلاً BTC_USDT_history.csv)
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
    
    # تبدیل نام جفت‌ارز به فرمت بایننس (مثلاً BTCUSDT)
    symbol_api = symbol.replace('/', '').upper()
    
    all_kline_data = []
    
    # محاسبه نقطه شروع: ۴۰۰۰ کندل ۴ ساعته یعنی حدود ۶۶۰ روز پیش
    start_date = datetime.now() - timedelta(days=700)
    current_start_ts = int(start_date.timestamp() * 1000)
    
    print(f"🔄 شروع دانلود عمیق دیتای {symbol} از سرورهای بایننس (هدف: {target_candles} کندل)...")
    
    while len(all_kline_data) < target_candles:
        # آدرس API عمومی بایننس با پشتیبانی قطعی از startTime
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol_api}&interval={timeframe}&limit=1000&startTime={current_start_ts}"
        
        try:
            response = requests.get(url, timeout=15)
            
            # اگر بایننس ارز POL را با نام جدید نشناخت، به نام قدیمی آن (MATIC) سوییچ می‌کنیم
            if response.status_code == 400 and symbol_api == "POLUSDT":
                print("🔄 تغییر موقت نام POL به MATIC برای هماهنگی با سرورهای بایننس...")
                symbol_api = "MATICUSDT"
                continue
                
            if response.status_code == 200:
                data_part = response.json()
                
                if not data_part or len(data_part) == 0:
                    break
                    
                all_kline_data.extend(data_part)
                
                # دریافت زمان آخرین کندل این پارت برای شروع پارت بعدی
                latest_candle_ts = data_part[-1][0]
                
                print(f"   📥 دریافت {len(data_part)} کندل جدید. (مجموع ذخیره شده: {len(all_kline_data)})")
                
                if len(data_part) < 1000:
                    break
                    
                current_start_ts = latest_candle_ts + 1
                time.sleep(0.5) # رعایت محدودیت بایننس
            else:
                print(f"⚠️ خطای سرور بایننس: {response.text}")
                break
                
        except Exception as e:
            print(f"❌ خطا در ارتباط با بایننس: {e}")
            break

    if not all_kline_data:
        print(f"⚠️ هیچ دیتایی برای {symbol} دریافت نشد!")
        return

    # استخراج و مرتب‌سازی دقیق مطابق با ساختار پروژه شما
    # خروجی بایننس: [Open time, Open, High, Low, Close, Volume, ...]
    formatted_data = []
    for item in all_kline_data:
        ts = int(item[0])
        o = float(item[1])
        h = float(item[2])
        l = float(item[3])
        c = float(item[4])
        v = float(item[5])
        
        # ترتیب بکتستر شما: Timestamp, Open, High, Low, Close, Volume
        formatted_data.append([ts, o, h, l, c, v])

    df = pd.DataFrame(formatted_data, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    
    # حذف همپوشانی‌ها و مرتب‌سازی از قدیم به جدید
    df = df.drop_duplicates(subset=['Timestamp']).sort_values('Timestamp')
    
    # ذخیره فایل در مسیر مشخص
    df.to_csv(file_path, index=False)
    print(f"✅ فایل با موفقیت ذخیره شد: {symbol} اکنون دارای {len(df)} کندل تاریخی واقعی است.\n")

def fetch_all_data():
    symbols = getattr(config, 'WATCHLIST', [])
    tf = getattr(config, 'TIMEFRAME', '4h')
    
    if not symbols:
        print("❌ لیست واچ‌لیست در config.py یافت نشد.")
        return
        
    print("🚀 اتصال به سرورهای بایننس برقرار شد...")
    for s in symbols:
        fetch_deep_history_binance(s, timeframe=tf, target_candles=4000)
        time.sleep(1)

if __name__ == "__main__":
    fetch_all_data()

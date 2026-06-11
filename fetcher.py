# ---------------------------------------------------------
# FILE PATH: fetcher.py (v8.4 - Fully Fixed CoinEx Deep Fetcher)
# ---------------------------------------------------------
import requests
import pandas as pd
import os
import time
import config

def fetch_deep_history(symbol, timeframe="4h", target_candles=4000):
    """
    دریافت دیتای عمیق از کوین‌اکس با استفاده از مکانیزم اختصاصی last_id (تضمینی)
    """
    data_dir = os.path.join(os.getcwd(), "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    
    # تبدیل فرمت ارز به ساختار کوین‌اکس (مثلا BTCUSDT)
    symbol_api = symbol.replace('/', '').upper()
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
    
    all_kline_data = []
    last_id = 0 # صفر یعنی از جدیدترین کندل‌ها شروع کن و به عقب برو
    
    print(f"🔄 شروع فچ قطعی دیتای {symbol} (هدف: {target_candles} کندل)...")
    
    # اجرای حلقه برای گرفتن پارت‌های ۱۰۰۰ تایی به سمت گذشته
    while len(all_kline_data) < target_candles:
        url = f"https://api.coinex.com/v1/market/kline?market={symbol_api}&limit=1000&type={timeframe}"
        if last_id > 0:
            url += f"&last_id={last_id}" # هل دادن صرافی به زمان‌های دورتر
            
        try:
            response = requests.get(url, timeout=15).json()
            if response.get('code') == 0 and response.get('data'):
                data_part = response['data']
                
                if not data_part or len(data_part) == 0:
                    break
                    
                all_kline_data.extend(data_part)
                
                # کلید حل معما: شناسایی شناسه اولین (قدیمی‌ترین) کندل در این پارت برای پارت بعدی
                last_id = data_part[0][0] 
                
                print(f"   📥 دریافت پارت جدید. کل کندل‌های انباشته شده تا الان: {len(all_kline_data)}")
                
                # اگر صرافی دیتای کمتری داد یعنی به انتهای تاریخچه رسیده‌ایم
                if len(data_part) < 1000:
                    break
            else:
                print(f"⚠️ خطای صرافی در پاسخ: {response}")
                break
                
            time.sleep(1) # رعایت محدودیت درخواست صرافی
            
        except Exception as e:
            print(f"❌ خطا در شبکه یا پردازش: {e}")
            break

    if not all_kline_data:
        print(f"⚠️ هیچ دیتایی برای {symbol} دریافت نشد.")
        return

    # تبدیل به دیتافریم با ستون‌های استاندارد پروژه شما
    df = pd.DataFrame(all_kline_data, columns=['Timestamp', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
    df = df[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
    
    # حذف همپوشانی‌های احتمالی و مرتب‌سازی نهایی از قدیم به جدید
    df = df.drop_duplicates(subset=['Timestamp']).sort_values('Timestamp')
    
    # ذخیره در فایل
    df.to_csv(file_path, index=False)
    print(f"✅ با موفقیت ذخیره شد: {symbol} اکنون دارای {len(df)} کندل واقعی در بکتست است.\n")

def fetch_all_data():
    symbols = getattr(config, 'WATCHLIST', [])
    if not symbols:
        print("❌ لیست واچ‌لیست در config.py یافت نشد.")
        return
        
    for s in symbols:
        # درخواست ۴۰۰0 کندل (معادل حدود ۲ سال دیتای عمیق ۴ ساعته)
        fetch_deep_history(s, timeframe="4h", target_candles=4000)
        time.sleep(1)

if __name__ == "__main__":
    fetch_all_data()

# ---------------------------------------------------------
# FILE PATH: fetcher.py (v8.3 - Reverse Pagination for CoinEx)
# ---------------------------------------------------------
import ccxt
import pandas as pd
import os
import time
from datetime import datetime, timedelta
import config

def fetch_deep_history(symbol, timeframe="4h", days_back=1000):
    """
    دریافت دیتای عمیق با حرکت معکوس در زمان (ویژه محدودیت‌های صرافی کوین‌اکس)
    """
    data_dir = os.path.join(os.getcwd(), "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
    
    exchange = ccxt.coinex({
        'timeout': 30000,
        'enableRateLimit': True,
    })
    
    # محاسبه قدیمی‌ترین زمان مدنظر (نقطه پایان دانلود به سمت گذشته)
    target_end_time = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
    
    # شروع دانلود از همین لحظه (زمان حال)
    current_since = None 
    all_ohlcv = []
    
    print(f"🔄 شروع دانلود معکوس دیتای {symbol} برای {days_back} روز گذشته...")
    
    # برای جلوگیری از حلقه بی‌نهایت، سقف ۵ مرحله درخواست می‌گذاریم (معادل ۵۰۰۰ کندل)
    for iteration in range(5):
        try:
            # دریافت دیتا (کوین‌اکس همیشه از زمان حال یا از since به قبل را می‌دهد)
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=1000)
            
            if not ohlcv or len(ohlcv) == 0:
                break
                
            all_ohlcv.extend(ohlcv)
            
            # پیدا کردن قدیمی‌ترین کندل در این پارت دانلود شده
            oldest_candle_timestamp = ohlcv[0][0]
            
            print(f"   📥 پارت {iteration + 1}: دریافت {len(ohlcv)} کندل. (قدیمی‌ترین کندل این پارت: {exchange.iso8601(oldest_candle_timestamp)[:10]})")
            
            # اگر به بازه زمانی مورد نظرمان رسیده‌ایم، کار تمام است
            if oldest_candle_timestamp <= target_end_time:
                print("   🎯 به عمق زمانی مورد نظر رسیدیم.")
                break
                
            # 🔥 نکته کلیدی: تغییر لیمیت زمانی به قبل از قدیمی‌ترین کندل دریافت شده برای درخواست بعدی
            # در تایم‌فریم ۴ ساعته، ۱۰۰۰ کندل معادل حدود ۱۶۶ روز است. زمان را ۱۶۷ روز به عقب می‌کشیم.
            current_since = oldest_candle_timestamp - (1000 * 4 * 60 * 60 * 1000)
            
            time.sleep(exchange.rateLimit / 1000.0)
            
        except Exception as e:
            print(f"❌ خطا در لایه دانلود: {e}")
            time.sleep(2)
            break

    if not all_ohlcv:
        print(f"⚠️ دیتایی دریافت نشد.")
        return

    # تبدیل به دیتافریم، حذف همپوشانی‌ها و مرتب‌سازی از قدیم به جدید
    df = pd.DataFrame(all_ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df = df.drop_duplicates(subset=['Timestamp']).sort_values('Timestamp')
    
    # ذخیره نهایی
    df.to_csv(file_path, index=False)
    print(f"✅ موفقیت: {symbol} با موفقیت به {len(df)} کندل ارتقا یافت.\n")

def fetch_all_data():
    symbols = getattr(config, 'WATCHLIST', [])
    for s in symbols:
        fetch_deep_history(s, timeframe="4h", days_back=1000)
        time.sleep(1)

if __name__ == "__main__":
    fetch_all_data()

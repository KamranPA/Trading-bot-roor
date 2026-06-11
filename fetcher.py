# ---------------------------------------------------------
# FILE PATH: fetcher.py (v8.2 - Deep Historical Pagination)
# ---------------------------------------------------------
import ccxt
import pandas as pd
import os
import time
from datetime import datetime, timedelta
import config

def fetch_deep_history(symbol, timeframe="4h", days_back=1000):
    """
    دریافت دیتای تاریخی عمیق با استفاده از CCXT و صفحه‌بندی زمانی (Pagination)
    days_back: تعداد روزهایی که می‌خواهیم به عقب برگردیم (پیش‌فرض ۱۰۰۰ روز معادل حدود ۳ سال)
    """
    # ایجاد پوشه بر اساس تایم‌فریم
    data_dir = os.path.join(os.getcwd(), "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
    
    # راه‌اندازی کلاینت عمومی کوین‌اکس
    exchange = ccxt.coinex({
        'timeout': 30000,
        'enableRateLimit': True,
    })
    
    # محاسبه نقطه شروع زمانی (Timestamp)
    since = int((datetime.now() - timedelta(days=days_back)).timestamp() * 1000)
    
    all_ohlcv = []
    print(f"🔄 در حال فچ کردن دیتای عمیق {symbol} برای {days_back} روز گذشته (تایم‌فریم {timeframe})...")
    
    while True:
        try:
            # دریافت دیتا از نقطه since
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            
            if not ohlcv or len(ohlcv) == 0:
                break
                
            all_ohlcv.extend(ohlcv)
            
            # تنظیم نقطه شروع بعدی روی آخرین کندل دریافت شده + 1 میلی‌ثانیه
            since = ohlcv[-1][0] + 1 
            
            print(f"   📥 دریافت {len(ohlcv)} کندل جدید... (تا تاریخ {exchange.iso8601(since)[:10]})")
            
            # اگر صرافی کمتر از 1000 کندل برگرداند، یعنی به زمان حال رسیده‌ایم
            if len(ohlcv) < 1000:
                break
                
            # مکث کوتاه برای جلوگیری از مسدود شدن توسط صرافی (Rate Limit)
            time.sleep(exchange.rateLimit / 1000.0)
            
        except Exception as e:
            print(f"❌ خطا در دریافت دیتای {symbol}: {e}")
            time.sleep(5) # در صورت بروز خطای شبکه، 5 ثانیه صبر کرده و مجدد تلاش می‌کند
            break

    if not all_ohlcv:
        print(f"⚠️ هیچ دیتایی برای {symbol} یافت نشد.")
        return

    # تبدیل داده‌ها به دیتافریم استاندارد با همان فرمت قبلی
    df = pd.DataFrame(all_ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    
    # تبدیل مقادیر به اعشاری برای جلوگیری از باگ‌های محاسباتی
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = df[col].astype(float)
        
    # در این نسخه چون دیتای بسیار عمیقی می‌گیریم، دیتای قبلی را کاملا جایگزین می‌کنیم 
    # تا تداخلی در فرمت‌های زمانی (ثانیه/میلی‌ثانیه) پیش نیاید
    df = df.drop_duplicates(subset=['Timestamp']).sort_values('Timestamp')
    df.to_csv(file_path, index=False)
    
    print(f"✅ موفقیت نهایی: ارز {symbol} اکنون دارای {len(df)} کندل تاریخی است.\n")

def fetch_all_data():
    symbols = getattr(config, 'WATCHLIST', [])
    if not symbols:
        print("❌ لیست WATCHLIST در config.py خالی است!")
        return

    print(f"🚀 شروع دانلود دیتای عمیق برای {len(symbols)} ارز (برای بکتست قدرتمندتر)...")
    print("=" * 60)

    for s in symbols:
        # ۱. دریافت دیتای ۴ ساعته (۱۰۰۰ روز گذشته = تقریبا ۳ سال / شامل حدود ۶۰۰۰ کندل)
        fetch_deep_history(s, timeframe="4h", days_back=1000)
        
        # وقفه بین ارزها
        time.sleep(1)

        # ۲. در صورت نیاز به دیتای ۳۰ دقیقه‌ای، می‌توانید این خط را از حالت کامنت خارج کنید
        # fetch_deep_history(s, timeframe="30m", days_back=300)

if __name__ == "__main__":
    fetch_all_data()

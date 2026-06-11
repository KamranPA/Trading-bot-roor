import ccxt
import pandas as pd
import os
import time
import config

def fetch_data_full(symbol, timeframe="4h"):
    """
    دریافت ۴۰۰۰ کندل به صورت مرحله‌ای (۱۰۰۰ تایی) برای دور زدن محدودیت‌های صرافی
    """
    data_dir = os.path.join(os.getcwd(), "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, f"{symbol.replace('/', '_')}_history.csv")
    
    # تعریف دو صرافی برای سیستم جایگزین (Fallback)
    exchanges = {
        'binance': ccxt.binance({'enableRateLimit': True}),
        'coinex': ccxt.coinex({'enableRateLimit': True})
    }
    
    all_data = []
    # تاریخ شروع: حدود ۶۶۰ روز قبل
    since = int((time.time() - (4000 * 4 * 60 * 60)) * 1000)
    
    print(f"🔄 شروع فرآیند دانلود برای {symbol}...")

    for ex_name, ex_obj in exchanges.items():
        try:
            # تنظیم نماد (بایننس بدون اسلش، کوین‌اکس با اسلش)
            symbol_fmt = symbol.replace('/', '') if ex_name == 'binance' else symbol
            
            current_since = since
            for i in range(4): # ۴ مرحله برای رسیدن به ۴۰۰۰ کندل
                ohlcv = ex_obj.fetch_ohlcv(symbol_fmt, timeframe, since=current_since, limit=1000)
                if not ohlcv: break
                
                all_data.extend(ohlcv)
                current_since = ohlcv[-1][0] + 1
                time.sleep(0.6) # جلوگیری از بلاک شدن توسط صرافی
            
            if all_data:
                print(f"✅ دریافت موفقیت‌آمیز از {ex_name}")
                break # اگر دیتا گرفتیم، دیگر به صرافی بعدی نمی‌رویم
        except Exception as e:
            print(f"⚠️ تلاش از {ex_name} ناموفق بود: {str(e)[:50]}...")
            continue

    if all_data:
        df = pd.DataFrame(all_data, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df = df.drop_duplicates(subset=['Timestamp']).sort_values('Timestamp')
        df.to_csv(file_path, index=False)
        print(f"🚀 مجموع {len(df)} کندل برای {symbol} نهایی شد.")
    else:
        print(f"❌ شکست نهایی در دریافت دیتای {symbol}")

def fetch_all_data():
    symbols = getattr(config, 'WATCHLIST', [])
    tf = getattr(config, 'TIMEFRAME', '4h')
    for s in symbols:
        fetch_data_full(s, tf)

if __name__ == "__main__":
    fetch_all_data()

# ---------------------------------------------------------
# FILE PATH: fetcher.py (Final Optimized Version)
# ---------------------------------------------------------
import ccxt
import pandas as pd
import os
import time
import config

def save_data(df, symbol, timeframe):
    """ذخیره دیتای استاندارد شده در مسیر بکتستر"""
    data_dir = os.path.join(os.getcwd(), "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, f"{symbol.replace('/', '_')}_history.csv")
    df.to_csv(file_path, index=False)
    print(f"✅ فایل نهایی برای {symbol} با {len(df)} کندل ذخیره شد.")

def fetch_data(symbol, timeframe="4h"):
    # 1. تلاش برای دانلود از بایننس (موتور اصلی)
    try:
        binance = ccxt.binance({'enableRateLimit': True})
        # دریافت ۴۰۰۰ کندل در ۴ مرحله ۱۰۰۰ تایی
        all_ohlcv = []
        since = binance.parse8601('2024-01-01T00:00:00Z') # شروع از ابتدای ۲۰۲۴
        
        for _ in range(4):
            ohlcv = binance.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            if not ohlcv: break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            time.sleep(0.5)
            
        if all_ohlcv:
            df = pd.DataFrame(all_ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            save_data(df, symbol, timeframe)
            return
    except Exception as e:
        print(f"⚠️ بایننس در دسترس نیست برای {symbol}: {e}")

    # 2. موتور جایگزین (کوین‌اکس) در صورت شکست بایننس
    try:
        print(f"🔄 استفاده از موتور جایگزین کوین‌اکس برای {symbol}")
        coinex = ccxt.coinex({'enableRateLimit': True})
        ohlcv = coinex.fetch_ohlcv(symbol, timeframe, limit=1000)
        df = pd.DataFrame(ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        save_data(df, symbol, timeframe)
    except Exception as e:
        print(f"❌ شکست کامل برای {symbol}: {e}")

def fetch_all_data():
    symbols = getattr(config, 'WATCHLIST', [])
    tf = getattr(config, 'TIMEFRAME', '4h')
    
    print(f"🚀 شروع فرآیند دانلود هیبریدی برای {len(symbols)} ارز...")
    for s in symbols:
        fetch_data(s, tf)
        time.sleep(1)

if __name__ == "__main__":
    fetch_all_data()

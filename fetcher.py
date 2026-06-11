# ---------------------------------------------------------
# FILE PATH: fetcher.py (v9.1 - Hybrid Binance + CoinEx Engine)
# ---------------------------------------------------------
import ccxt
import pandas as pd
import os
import time
import config

def fetch_data_robust(symbol, timeframe="4h"):
    """نسخه نهایی با استفاده از CCXT و هدرهای مرورگر برای دور زدن محدودیت‌ها"""
    data_dir = os.path.join(os.getcwd(), "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, f"{symbol.replace('/', '_')}_history.csv")
    
    # تنظیمات حرفه‌ای صرافی (مهم‌ترین بخش برای عبور از خطاها)
    exchange = ccxt.coinex({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'},
        'headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    })

    try:
        print(f"🔄 تلاش برای دریافت دیتا با تنظیمات مرورگر برای: {symbol}")
        # دریافت دیتا به صورت اسلایسی (برای کوین‌اکس)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=1000)
        
        if not ohlcv:
            print(f"❌ شکست مجدد برای {symbol}")
            return False

        df = pd.DataFrame(ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df.to_csv(file_path, index=False)
        print(f"✅ موفقیت: {len(df)} کندل دریافت شد.")
        return True

    except Exception as e:
        print(f"❌ خطا در CCXT: {e}")
        return False

def fetch_all_data():
    symbols = getattr(config, 'WATCHLIST', [])
    for s in symbols:
        if not fetch_data_robust(s):
            # اگر با کوین‌اکس نشد، یک بار هم روی بایننس با همین تنظیمات امتحان می‌کند
            print(f"⚠️ انتقال به موتور بایننس برای {s}...")
            # کد کوتاه شده برای امتحان بایننس
            try:
                binance = ccxt.binance({'enableRateLimit': True})
                ohlcv = binance.fetch_ohlcv(s, '4h', limit=1000)
                df = pd.DataFrame(ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
                df.to_csv(f"data/4h/{s.replace('/', '_')}_history.csv", index=False)
            except:
                print(f"🚨 شکست نهایی برای {s}")
        time.sleep(2)

if __name__ == "__main__":
    fetch_all_data()

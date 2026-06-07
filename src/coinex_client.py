# ---------------------------------------------------------
# FILE PATH: /src/coinex_client.py
# ---------------------------------------------------------

import ccxt
import pandas as pd
import time
import config

def get_coinex_candles(pair):
    """
    دریافت کندل‌ها با مدیریت نرخ درخواست برای جلوگیری از بلاک شدن در واچ‌لیست ۱۵ تایی
    """
    try:
        # تنظیمات بهینه برای ارتباط پایدار با کوین‌اکس
        exchange = ccxt.coinex({
            'timeout': 20000,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        })
        
        # وقفه کوچک برای جلوگیری از فشار همزمان روی API صرافی (بسیار مهم برای ۱۵ ارز)
        time.sleep(0.6) 
        
        ohlcv = exchange.fetch_ohlcv(
            symbol=pair, 
            timeframe=config.TIMEFRAME, 
            limit=config.CANDLES_LIMIT
        )
        
        if not ohlcv or len(ohlcv) < config.CANDLES_LIMIT:
            print(f"⚠️ داده‌های ناقص برای {pair} دریافت شد.")
            return None
            
        columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
        df = pd.DataFrame(ohlcv, columns=columns)
        
        # تبدیل تمامی ستون‌های عددی به float برای محاسبات ریاضی دقیق در سیستم ۱۰‌بعدی
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        df[numeric_cols] = df[numeric_cols].astype(float)
        
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
        
        return df

    except Exception as e:
        print(f"❌ خطای ارتباط با API کوئینکس برای ارز {pair}: {e}")
        return None

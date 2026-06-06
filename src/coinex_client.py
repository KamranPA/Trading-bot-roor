# src/coinex_client.py
# ماژول رسمی اتصال به API صرافی کوئینکس و دریافت کندل‌ها

import ccxt
import pandas as pd
import config  # فراخوانی تنظیمات مرکزی برای حفظ ساختار ماژولار

def get_coinex_candles(pair):
    """
    دریافت ۱۰۰ کندل اخیر ۴ ساعته برای یک جفت‌ارز مشخص از صرافی کوئینکس
    """
    try:
        # اتصال به صرافی کوئینکس به صورت عمومی (بدون نیاز به کلید خصوصی)
        exchange = ccxt.coinex({
            'timeout': 15000,
            'enableRateLimit': True, # احترام به محدودیت تعداد درخواست صرافی برای جلوگیری از بلاک شدن
        })
        
        # دریافت داده‌های OHLCV (Open, High, Low, Close, Volume)
        ohlcv = exchange.fetch_ohlcv(
            symbol=pair, 
            timeframe=config.TIMEFRAME, 
            limit=config.CANDLES_LIMIT
        )
        
        if not ohlcv:
            print(f"⚠️ هیچ دیتایی برای {pair} دریافت نشد.")
            return None
            
        # تبدیل لیست خام به یک جدول منظم (Dataframe)
        columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
        df = pd.DataFrame(ohlcv, columns=columns)
        
        # تبدیل زمان میلی‌ثانیه صرافی به تاریخ و ساعت استاندارد
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
        
        return df

    except Exception as e:
        print(f"❌ خطا در ارتباط با API کوئینکس برای ارز {pair}: {e}")
        return None

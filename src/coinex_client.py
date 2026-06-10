# ---------------------------------------------------------
# FILE PATH: src/coinex_client.py
# ---------------------------------------------------------
import ccxt
import pandas as pd
import logging

def get_coinex_candles(pair, timeframe="4h", limit=500):
    """
    دریافت کندل‌های بازار از طریق API عمومی کوین‌اکس بدون نیاز به کلید خصوصی
    """
    try:
        # اتصال عمومی و بدون نیاز به API Key برای مانیتورینگ بازار
        exchange = ccxt.coinex({
            'timeout': 30000,
            'enableRateLimit': True,
        })
        
        # هماهنگ‌سازی فرمت جفت ارز (مثلاً تبدیل BTC/USDT به فرمت استاندارد ccxt)
        symbol = pair.upper()
        
        logging.info(f"🔄 در حال دریافت {limit} کندل برای {symbol} در تایم‌فریم {timeframe}...")
        
        # دریافت دیتای OHLCV از صرافی
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        if not ohlcv or len(ohlcv) == 0:
            logging.warning(f"⚠️ هیچ دیتایی برای {symbol} دریافت نشد.")
            return None
            
        # تبدیل به DataFrame استاندارد پانداز
        df = pd.DataFrame(ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        
        # تبدیل انواع داده‌ها به عدد اعشاری برای جلوگیری از خطای محاسباتی اندیکاتورها
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = df[col].astype(float)
            
        return df

    except Exception as e:
        logging.error(f"❌ خطا در دریافت دیتا از کوین‌اکس برای {pair}: {e}")
        return None

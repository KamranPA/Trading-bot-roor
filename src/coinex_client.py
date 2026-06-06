# src/coinex_client.py
# ماژول یکپارچه اتصال به API صرافی کوئینکس (دریافت داده + اجرای پوزیشن)

import ccxt
import pandas as pd
import config 

def get_coinex_candles(pair):
    """دریافت کندل‌های ۴ ساعته برای تحلیل"""
    try:
        exchange = ccxt.coinex({'enableRateLimit': True})
        ohlcv = exchange.fetch_ohlcv(pair, timeframe=config.TIMEFRAME, limit=config.CANDLES_LIMIT)
        
        if not ohlcv: return None
            
        columns = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
        df = pd.DataFrame(ohlcv, columns=columns)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"❌ خطا در دریافت دیتای {pair}: {e}")
        return None

def open_position(signal_data):
    """اجرای سفارش خرید یا فروش در صرافی"""
    try:
        # اتصال امن با کلیدهای API
        exchange = ccxt.coinex({
            'apiKey': config.API_KEY,
            'secret': config.SECRET_KEY,
            'enableRateLimit': True,
        })
        
        symbol = signal_data['pair']
        # محاسبه جهت سفارش
        side = 'buy' if signal_data['direction'] == 'LONG' else 'sell'
        amount = signal_data['position_size']
        
        # ثبت سفارش در مارکت
        order = exchange.create_market_order(symbol, side, amount)
        print(f"✅ پوزیشن {side} برای {symbol} ثبت شد. ID: {order['id']}")
        return order
        
    except Exception as e:
        print(f"❌ خطا در باز کردن پوزیشن در صرافی: {e}")
        return None

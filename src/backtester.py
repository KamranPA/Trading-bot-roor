# ---------------------------------------------------------
# FILE NAME: backtester.py
# FILE PATH: /src/backtester.py
# ---------------------------------------------------------
import pandas as pd
import logging
from src import coinex_client, strategy_utils, strategy

def run_backtest(symbol, days=30):
    """
    اجرای بکتست برای یک نماد خاص
    بدون استفاده از ماژول حذف شده indicators
    """
    logging.info(f"🔍 شروع بکتست برای {symbol}")
    
    try:
        # ۱. دریافت داده‌ها
        df = coinex_client.get_coinex_candles(symbol)
        if df is None or df.empty:
            logging.error(f"❌ داده‌ای برای {symbol} یافت نشد.")
            return

        # ۲. محاسبه اندیکاتورها از طریق strategy_utils (منبع حقیقت واحد)
        df = strategy_utils.calculate_indicators(df)
        
        # ۳. شبیه‌سازی استراتژی
        # در اینجا منطق تست روی داده‌های تاریخی اجرا می‌شود
        results = []
        for i in range(len(df)):
            # منطق بکتست شما اینجا قرار می‌گیرد
            pass
            
        logging.info(f"✅ بکتست برای {symbol} با موفقیت پایان یافت.")
        return results

    except Exception as e:
        logging.error(f"❌ خطا در بکتست {symbol}: {e}")

if __name__ == "__main__":
    # تست اجرا
    run_backtest("BTC/USDT")

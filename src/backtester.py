# src/backtester.py
from src import coinex_client, indicators
import pandas as pd

def run_backtest():
    # لیست نمادها را از config یا یک لیست دستی بگیرید
    symbols = ['BTCUSDT', 'ETHUSDT'] 
    summary_data = {}
    total_trades = 0

    for symbol in symbols:
        try:
            # دریافت مستقیم دیتا از صرافی
            df = coinex_client.get_coinex_candles(symbol)
            if df is None or df.empty: continue
            
            # محاسبات
            df = indicators.calculate_indicators(df)
            # (منطق بررسی استراتژی شما)
            # ...
            
            summary_data[symbol] = (trades, wins)
            total_trades += trades
        except Exception as e:
            print(f"❌ خطا در دریافت دیتا برای {symbol}: {e}")

    # نوشتن گزارش
    with open('backtest_summary.txt', 'w', encoding='utf-8') as f:
        # ... (کد نوشتن گزارش) ...

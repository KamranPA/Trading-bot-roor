# ---------------------------------------------------------
# FILE NAME: backtester.py
# ---------------------------------------------------------
import pandas as pd
import os
from pathlib import Path
from src import coinex_client, indicators # فراخوانی مستقیم از src

def check_filters(row):
    """فیلترهای استراتژی"""
    try:
        # استفاده از .get برای جلوگیری از خطای ستون‌های خالی
        trend_ok = row.get('feat_trend_line', 0) == 1.0
        adx_ok = row.get('feat_adx', 0) > 15
        rsi_ok = row.get('feat_rsi', 50) < 75
        return trend_ok and adx_ok and rsi_ok
    except:
        return False

def run_backtest():
    # تعیین مسیر ریشه پروژه برای ذخیره فایل خروجی
    BASE_DIR = Path(__file__).resolve().parent.parent
    output_path = BASE_DIR / "backtest_summary.txt"
    
    # نمادهایی که می‌خواهید تست کنید
    symbols = ['BTCUSDT', 'ETHUSDT'] 
    summary_data = {}
    total_trades = 0

    print(f"🚀 شروع بک‌تست با دیتای مستقیم صرافی...")

    for symbol in symbols:
        try:
            # دریافت دیتا مستقیم از صرافی
            df = coinex_client.get_coinex_candles(symbol)
            if df is None or df.empty:
                print(f"⚠️ دیتایی برای {symbol} دریافت نشد.")
                continue
            
            df.columns = [c.capitalize() for c in df.columns]
            df = indicators.calculate_indicators(df)
            
            # محاسبات استراتژی
            mask = df.apply(check_filters, axis=1)
            entry_indices = df[mask].index
            
            trades, wins = 0, 0
            for idx in entry_indices:
                if idx + 5 >= len(df): continue
                
                entry_price = df.loc[idx, 'Close']
                future_price = df.loc[idx + 5, 'Close']
                if future_price > entry_price:
                    wins += 1
                trades += 1
            
            summary_data[symbol] = (trades, wins)
            total_trades += trades
            print(f"✅ پردازش {symbol} با {trades} معامله انجام شد.")
            
        except Exception as e:
            print(f"❌ خطا در پردازش {symbol}: {e}")

    # نوشتن گزارش نهایی در ریشه پروژه
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("📈 گزارش بکتست آنلاین (از صرافی)\n==============================\n")
        for s, (t, w) in summary_data.items():
            wr = (w / t * 100) if t > 0 else 0
            f.write(f"{s:10} | معاملات: {t:4} | نرخ برد: {wr:5.1f}%\n")
        f.write(f"==============================\n📊 مجموع معاملات: {total_trades}")
    
    print(f"✅ فایل گزارش در {output_path} ذخیره شد.")

if __name__ == "__main__": 
    run_backtest()

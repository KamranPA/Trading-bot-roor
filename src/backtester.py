# ---------------------------------------------------------
# FILE NAME: backtester.py
# FILE PATH: /src/backtester.py
# ---------------------------------------------------------
import pandas as pd
from pathlib import Path
from src import coinex_client, indicators
import config  # فراخوانی لیست ارزها از تنظیمات شما

def check_filters(row):
    """فیلترهای استراتژی معاملاتی"""
    try:
        trend_ok = row.get('feat_trend_line', 0) == 1.0
        adx_ok = row.get('feat_adx', 0) > 15
        rsi_ok = row.get('feat_rsi', 50) < 75
        return trend_ok and adx_ok and rsi_ok
    except:
        return False

def run_backtest():
    # تعیین مسیر خروجی در ریشه پروژه
    BASE_DIR = Path(__file__).resolve().parent.parent
    output_path = BASE_DIR / "backtest_summary.txt"
    
    # دریافت لیست ارزها از config.py
    symbols = getattr(config, 'WATCHLIST', [])
    
    if not symbols:
        print("❌ لیست ارزها (WATCHLIST) در config خالی است!")
        return

    print(f"🚀 شروع بک‌تست برای {len(symbols)} نماد...")
    
    summary_data = {}
    total_trades = 0

    for symbol in symbols:
        try:
            # دریافت مستقیم دیتا از صرافی
            df = coinex_client.get_coinex_candles(symbol)
            if df is None or df.empty:
                print(f"⚠️ دیتایی برای {symbol} دریافت نشد.")
                continue
            
            # استانداردسازی ستون‌ها و محاسبات
            df.columns = [c.capitalize() for c in df.columns]
            df = indicators.calculate_indicators(df)
            
            # پیدا کردن سیگنال‌ها
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
            print(f"✅ پردازش {symbol}: {trades} معامله.")
            
        except Exception as e:
            print(f"❌ خطا در پردازش {symbol}: {e}")

    # نوشتن گزارش نهایی
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("📈 گزارش بکتست آنلاین (از صرافی)\n==============================\n")
        for s, (t, w) in summary_data.items():
            wr = (w / t * 100) if t > 0 else 0
            f.write(f"{s:10} | معاملات: {t:4} | نرخ برد: {wr:5.1f}%\n")
        f.write(f"==============================\n📊 مجموع معاملات: {total_trades}")
    
    print(f"✅ گزارش در {output_path} ذخیره شد.")

if __name__ == "__main__": 
    run_backtest()

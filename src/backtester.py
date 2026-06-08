# ---------------------------------------------------------
# FILE NAME: backtester.py
# FILE PATH: /src/backtester.py
# ---------------------------------------------------------
import pandas as pd
import sqlite3
from pathlib import Path
from src import indicators

def check_filters(row):
    """
    سیستم جدید: فیلتر حجم حذف شد.
    فقط شرایط روند و مومنتوم بررسی می‌شود.
    """
    trend_ok = row['feat_trend_line'] == 1.0
    adx_ok = row['feat_adx'] > 15  # کاهش آستانه برای یافتن سیگنال
    rsi_ok = row['feat_rsi'] < 75  # فقط حذف حالت اشباع خرید شدید
    
    return trend_ok and adx_ok and rsi_ok

def run_backtest():
    base_dir = Path.cwd()
    data_dir = base_dir / "data"
    path_30m = data_dir / "30m"
    
    # استفاده از حلقه for برای پیمایش تمام فایل‌ها
    csv_files = list(path_30m.glob("*_history.csv"))
    print(f"DEBUG: تعداد فایل‌های پیدا شده برای بکتست: {len(csv_files)}")
    
    summary_data = {}
    total_trades = 0

    for file_path in csv_files:
        symbol = file_path.name.replace('_history.csv', '')
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.capitalize() for c in df.columns]
            df = indicators.calculate_indicators(df)
            
            # پیدا کردن نقاط ورود با فیلترهای جدید
            mask = df.apply(check_filters, axis=1)
            entry_indices = df[mask].index
            
            trades, wins = 0, 0
            for idx in entry_indices:
                if idx + 20 >= len(df): break
                
                entry_price = df.loc[idx, 'Close']
                # تست ساده سود/ضرر
                future_price = df.loc[idx + 5, 'Close']
                if future_price > entry_price:
                    wins += 1
                trades += 1
            
            summary_data[symbol] = (trades, wins)
            total_trades += trades
            
        except Exception as e:
            print(f"❌ خطا در پردازش {symbol}: {e}")

    # تولید گزارش
    with open('backtest_summary.txt', 'w', encoding='utf-8') as f:
        f.write("📈 گزارش بکتست (بدون فیلتر حجم)\n==============================\n")
        for s, (t, w) in summary_data.items():
            wr = (w / t * 100) if t > 0 else 0
            f.write(f"{s:10} | معاملات: {t:4} | نرخ برد: {wr:5.1f}%\n")
        f.write("==============================\n📊 مجموع معاملات: " + str(total_trades))

if __name__ == "__main__": 
    run_backtest()

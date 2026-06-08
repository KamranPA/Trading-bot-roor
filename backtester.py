# ---------------------------------------------------------
# FILE NAME: backtester.py
# FILE PATH: /src/backtester.py
# ---------------------------------------------------------
import pandas as pd
import sqlite3
from pathlib import Path
from src import indicators

def check_10_filters(row):
    """ارزیابی ۱۰ فاکتور سیستم هوش مصنوعی"""
    return (row['feat_trend_line'] == 1.0) and \
           (row['feat_adx'] > 25) and \
           (row['feat_vol_confirm'] == 1.0) and \
           (row['feat_rsi'] < 70) and \
           (row['feat_vol_ratio'] > 0.8)

def run_backtest():
    base_dir = Path.cwd()
    path_30m = base_dir / "data" / "30m"
    path_4h = base_dir / "data" / "4h"
    
    csv_files = list(path_30m.glob("*_history.csv"))
    summary_data = {}

    for file_path in csv_files:
        symbol = file_path.name.replace('_history.csv', '')
        try:
            df_30m = pd.read_csv(file_path)
            df_30m.columns = [c.capitalize() for c in df_30m.columns]
            df_30m = indicators.calculate_indicators(df_30m)
            
            # پیدا کردن نقاط ورود بر اساس ۱۰ فیلتر
            mask = df_30m.apply(check_10_filters, axis=1)
            entry_points = df_30m[mask].index

            wins, trades = 0, 0
            
            for idx in entry_points:
                if idx + 30 >= len(df_30m): break
                
                entry_price = df_30m.loc[idx, 'Close']
                atr = df_30m.loc[idx, 'Atr'] # استفاده از ATR محاسبه شده
                
                # تعیین حد سود و ضرر پویا
                dynamic_tp = atr * 3.0  # سود = 3 برابر نوسان
                dynamic_sl = atr * 1.5  # ضرر = 1.5 برابر نوسان
                
                for i in range(1, 30):
                    price = df_30m.loc[idx + i, 'Close']
                    diff = price - entry_price
                    
                    if diff >= dynamic_tp:
                        wins += 1
                        trades += 1
                        break
                    elif diff <= -dynamic_sl:
                        trades += 1
                        break
            
            summary_data[symbol] = (trades, wins)
        except Exception as e:
            print(f"❌ خطای پردازش {symbol}: {e}")

    # گزارش نهایی
    with open('backtest_summary.txt', 'w', encoding='utf-8') as f:
        f.write("🤖 گزارش بکتست سیستم ۱۰‌بعدی (Dynamic ATR-based)\n==================================\n")
        for s, (t, w) in summary_data.items():
            wr = (w / t * 100) if t > 0 else 0
            f.write(f"{s:10} | معاملات: {t:4} | نرخ برد: {wr:5.1f}%\n")
        f.write("==================================\n📊 پایان بکتست هوشمند.")

if __name__ == "__main__": 
    run_backtest()

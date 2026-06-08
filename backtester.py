# ---------------------------------------------------------
# FILE NAME: backtester.py
# FILE PATH: /src/backtester.py
# ---------------------------------------------------------
import pandas as pd
import sqlite3
from pathlib import Path
from src import indicators

def run_backtest():
    # تنظیمات ریسک و پاداش (این پارامترها را می‌توانید در config تغییر دهید)
    TAKE_PROFIT = 0.03  # ۳ درصد سود
    STOP_LOSS = 0.015   # ۱.۵ درصد ضرر
    
    base_dir = Path.cwd()
    path_30m = base_dir / "data" / "30m"
    path_4h = base_dir / "data" / "4h"
    
    csv_files = list(path_30m.glob("*_history.csv"))
    all_trades = [] 
    summary_data = {}

    for file_path in csv_files:
        symbol = file_path.name.replace('_history.csv', '')
        try:
            df_30m = pd.read_csv(file_path)
            df_4h = pd.read_csv(path_4h / file_path.name)
            
            df_30m.columns = [c.capitalize() for c in df_30m.columns]
            df_4h.columns = [c.capitalize() for c in df_4h.columns]
            
            df_30m = indicators.calculate_indicators(df_30m)
            df_4h = indicators.calculate_indicators(df_4h)
            
            if 'feat_trend_line' not in df_4h.columns or 'feat_adx' not in df_30m.columns:
                continue

            is_uptrend = df_4h['feat_trend_line'].iloc[-1] == 1.0
            mask = (df_30m['feat_adx'] > 25) & (df_30m['feat_vol_confirm'] == 1.0)
            entry_points = df_30m[mask].index

            wins = 0
            trades = 0
            
            for idx in entry_points:
                if idx + 20 >= len(df_30m): break # جلوگیری از خطای ایندکس
                
                entry_price = df_30m.loc[idx, 'Close']
                # بررسی قیمت‌های بعدی برای پیدا کردن TP یا SL
                for i in range(1, 20):
                    price = df_30m.loc[idx + i, 'Close']
                    pct_change = (price - entry_price) / entry_price if is_uptrend else (entry_price - price) / entry_price
                    
                    if pct_change >= TAKE_PROFIT:
                        wins += 1
                        trades += 1
                        break
                    elif pct_change <= -STOP_LOSS:
                        trades += 1
                        break
            
            summary_data[symbol] = (trades, wins)
            
        except Exception as e:
            print(f"❌ خطای پردازش {symbol}: {e}")

    # تولید گزارش نهایی
    with open('backtest_summary.txt', 'w', encoding='utf-8') as f:
        f.write("📈 گزارش راستی‌آزمایی (با حد سود 3% و حد ضرر 1.5%)\n==================================\n")
        total_trades = 0
        for s, (trades, wins) in summary_data.items():
            total_trades += trades
            win_rate = (wins / trades * 100) if trades > 0 else 0
            f.write(f"{s:10} | معاملات: {trades:4} | نرخ برد: {win_rate:5.1f}%\n")
        f.write("==================================\n📊 مجموع کل معاملات واقعی: " + str(total_trades))

if __name__ == "__main__": 
    run_backtest()

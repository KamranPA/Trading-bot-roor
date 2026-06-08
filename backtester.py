# ---------------------------------------------------------
# FILE NAME: backtester.py
# FILE PATH: /src/backtester.py
# ---------------------------------------------------------
import pandas as pd
import sqlite3
from pathlib import Path
from src import indicators

def check_10_filters(row):
    """
    ارزیابی سیستم ۱۰‌بعدی: 
    فقط در صورتی که فیلترهای اصلی برقرار باشند، معامله باز می‌شود.
    """
    # فیلترهای حیاتی (شما می‌توانید وزن‌دهی یا تغییر دهید)
    is_trend_up = row['feat_trend_line'] == 1.0
    is_adx_strong = row['feat_adx'] > 25
    is_vol_confirmed = row['feat_vol_confirm'] == 1.0
    is_rsi_safe = row['feat_rsi'] < 70 and row['feat_rsi'] > 30
    
    # فیلترهای تکمیلی سیستم ۱۰‌بعدی
    is_vol_ratio_ok = row['feat_vol_ratio'] > 0.8
    is_ema_dev_ok = abs(row['feat_ema_deviation']) < 5.0 # فاصله معقول از میانگین
    
    return is_trend_up and is_adx_strong and is_vol_confirmed and is_rsi_safe and is_vol_ratio_ok and is_ema_dev_ok

def run_backtest():
    TAKE_PROFIT = 0.03
    STOP_LOSS = 0.015
    
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
            
            # پیدا کردن نقاط ورود با استفاده از ۱۰ فیلتر
            # اعمال تابع بررسی روی تک‌تک ردیف‌ها
            mask = df_30m.apply(check_10_filters, axis=1)
            entry_points = df_30m[mask].index

            wins, trades = 0, 0
            
            for idx in entry_points:
                if idx + 20 >= len(df_30m): break
                
                entry_price = df_30m.loc[idx, 'Close']
                for i in range(1, 20):
                    price = df_30m.loc[idx + i, 'Close']
                    pct_change = (price - entry_price) / entry_price
                    
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

    # گزارش نهایی
    with open('backtest_summary.txt', 'w', encoding='utf-8') as f:
        f.write("🤖 گزارش بکتست سیستم ۱۰‌بعدی (Multi-Filter Strategy)\n==================================\n")
        total_t = 0
        for s, (t, w) in summary_data.items():
            total_t += t
            wr = (w / t * 100) if t > 0 else 0
            f.write(f"{s:10} | معاملات: {t:4} | نرخ برد: {wr:5.1f}%\n")
        f.write("==================================\n📊 مجموع معاملات هوشمند: " + str(total_t))

if __name__ == "__main__": 
    run_backtest()

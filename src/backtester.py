import pandas as pd
import sqlite3
import os
from pathlib import Path
from src import indicators

def check_filters(row):
    # چک کردن موجود بودن ستون‌ها برای جلوگیری از KeyError
    try:
        trend_ok = row.get('feat_trend_line', 0) == 1.0
        adx_ok = row.get('feat_adx', 0) > 15
        rsi_ok = row.get('feat_rsi', 50) < 75
        return trend_ok and adx_ok and rsi_ok
    except:
        return False

def run_backtest():
    # ۱. پیدا کردن مسیر دقیق ریشه پروژه
    BASE_DIR = Path(__file__).resolve().parent.parent
    # جستجو در data/30m نسبت به ریشه
    data_dir = BASE_DIR / "data" / "30m"
    
    # دیباگ مسیر
    print(f"DEBUG: BASE_DIR is {BASE_DIR}")
    print(f"DEBUG: Looking for files in {data_dir}")
    
    if not data_dir.exists():
        print(f"❌ خطا: پوشه {data_dir} پیدا نشد!")
        # لیست کردن محتویات ریشه برای درک ساختار
        print(f"DEBUG: Root contents: {list(BASE_DIR.iterdir())}")
        return

    csv_files = list(data_dir.glob("*_history.csv"))
    print(f"DEBUG: تعداد فایل‌های پیدا شده: {len(csv_files)}")
    
    summary_data = {}
    total_trades = 0

    for file_path in csv_files:
        symbol = file_path.name.replace('_history.csv', '')
        try:
            df = pd.read_csv(file_path)
            # تبدیل نام ستون‌ها به استاندارد
            df.columns = [c.capitalize() for c in df.columns]
            df = indicators.calculate_indicators(df)
            
            mask = df.apply(check_filters, axis=1)
            entry_indices = df[mask].index
            
            trades, wins = 0, 0
            for idx in entry_indices:
                if idx + 5 >= len(df): continue # جلوگیری از IndexOutOfBounds
                
                entry_price = df.loc[idx, 'Close']
                future_price = df.loc[idx + 5, 'Close']
                if future_price > entry_price:
                    wins += 1
                trades += 1
            
            summary_data[symbol] = (trades, wins)
            total_trades += trades
            
        except Exception as e:
            print(f"❌ خطا در پردازش {symbol}: {e}")

    # ۲. ذخیره فایل در مسیر مطلق (ریشه پروژه)
    output_path = BASE_DIR / "backtest_summary.txt"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("📈 گزارش بکتست (بدون فیلتر حجم)\n==============================\n")
        for s, (t, w) in summary_data.items():
            wr = (w / t * 100) if t > 0 else 0
            f.write(f"{s:10} | معاملات: {t:4} | نرخ برد: {wr:5.1f}%\n")
        f.write(f"==============================\n📊 مجموع معاملات: {total_trades}")
    
    print(f"✅ گزارش در {output_path} ذخیره شد.")

if __name__ == "__main__": 
    run_backtest()

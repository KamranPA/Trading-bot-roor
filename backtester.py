# ---------------------------------------------------------
# FILE NAME: backtester.py
# FILE PATH: /src/backtester.py
# ---------------------------------------------------------
import pandas as pd
import os
import sqlite3
from pathlib import Path
from src import indicators

def run_backtest():
    base_dir = Path.cwd()
    data_dir = base_dir / "data"
    # مسیر جدید دیتاها
    path_30m = data_dir / "30m"
    path_4h = data_dir / "4h"
    db_path = data_dir / "trading_bot.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS signals")
    cursor.execute("""
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, symbol TEXT, direction TEXT, 
            entry_price REAL, pnl_percent REAL, feat_adx REAL
        )
    """)
    
    csv_files = list(path_30m.glob("*_history.csv"))
    all_trades = [] 
    summary_data = {}

    for file_path in csv_files:
        symbol = file_path.name.replace('_history.csv', '')
        try:
            # ۱. خواندن دیتای ورود (30m)
            df_30m = pd.read_csv(file_path)
            # ۲. خواندن دیتای روند (4h) - فرض بر این است که فایل 4h هم با همین نام موجود است
            df_4h = pd.read_csv(path_4h / file_path.name)
            
            # استانداردسازی ستون‌ها
            df_30m.columns = [c.capitalize() for c in df_30m.columns]
            df_4h.columns = [c.capitalize() for c in df_4h.columns]
            
            # محاسبه ایندیکاتورها (فراخوانی تابع شما)
            df_30m = indicators.calculate_indicators(df_30m)
            df_4h = indicators.calculate_indicators(df_4h)
            
            # بررسی صحت ستون‌ها (اصلاح کیس-سنیتیویتی)
            # در indicators.py ستون‌ها بصورت 'feat_adx' با حروف کوچک تعریف شده‌اند
            adx_col = 'feat_adx'
            vol_col = 'feat_vol_confirm'
            trend_col = 'feat_trend_line'
            
            # منطق چندزمانی: فیلتر روند از 4h و سیگنال از 30m
            # اگر در 4h روند صعودی بود (feat_trend_line == 1)
            is_uptrend = df_4h[trend_col].iloc[-1] == 1.0
            
            mask = (df_30m[adx_col] > 25) & (df_30m[vol_col] == 1.0)
            trades_df = df_30m[mask].copy()
            
            if not trades_df.empty:
                # استفاده از فیلتر روند 4 ساعته برای تعیین جهت
                trades_df['Direction'] = 'LONG' if is_uptrend else 'SHORT'
                
                future_close = df_30m['Close'].shift(-5)
                trades_df['Pnl'] = ((future_close - trades_df['Close']) / trades_df['Close']) * 100
                trades_df['Pnl'] = trades_df.apply(lambda x: x['Pnl'] if x['Direction'] == 'LONG' else -x['Pnl'], axis=1)
                
                for _, row in trades_df.iterrows():
                    all_trades.append((row['Timestamp'], symbol, row['Direction'], row['Close'], row['Pnl'], row[adx_col]))
                
                summary_data[symbol] = (len(trades_df), len(trades_df[trades_df['Pnl'] > 0]))
            else:
                summary_data[symbol] = (0, 0)
            
        except Exception as e:
            print(f"⚠️ خطا در پردازش {symbol}: {e}")

    if all_trades:
        cursor.executemany("INSERT INTO signals (timestamp, symbol, direction, entry_price, pnl_percent, feat_adx) VALUES (?, ?, ?, ?, ?, ?)", all_trades)
    
    conn.commit()
    conn.close()
    
    with open('backtest_summary.txt', 'w', encoding='utf-8') as f:
        f.write("📈 گزارش بکتست چندزمانی (4H + 30m)\n==================================\n")
        for s, (trades, wins) in summary_data.items():
            win_rate = (wins / trades * 100) if trades > 0 else 0
            f.write(f"{s:10} | معاملات: {trades:4} | نرخ برد: {win_rate:5.1f}%\n")
        f.write("==================================\n📊 مجموع کل معاملات: " + str(len(all_trades)))

if __name__ == "__main__": 
    run_backtest()

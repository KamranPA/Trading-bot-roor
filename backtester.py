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
        file_4h_path = path_4h / file_path.name
        
        try:
            # ۱. خواندن دیتا
            df_30m = pd.read_csv(file_path)
            df_4h = pd.read_csv(file_4h_path)
            
            # استانداردسازی اولیه
            df_30m.columns = [c.capitalize() for c in df_30m.columns]
            df_4h.columns = [c.capitalize() for c in df_4h.columns]
            
            # محاسبه ایندیکاتورها (با نام‌های یکپارچه)
            df_30m = indicators.calculate_indicators(df_30m)
            df_4h = indicators.calculate_indicators(df_4h)
            
            # ۲. بررسی اینکه ایندیکاتورها ساخته شده‌اند
            # نام‌های استانداردِ جدید: feat_adx, feat_vol_confirm, feat_trend_line
            if 'feat_trend_line' not in df_4h.columns or 'feat_adx' not in df_30m.columns:
                print(f"⚠️ هشدار: دیتای کافی برای محاسبه ایندیکاتورهای {symbol} وجود ندارد.")
                summary_data[symbol] = (0, 0)
                continue

            # ۳. منطق استراتژی
            is_uptrend = df_4h['feat_trend_line'].iloc[-1] == 1.0
            
            # شرط ورود (بدون تغییر در ADX فعلاً)
            mask = (df_30m['feat_adx'] > 25) & (df_30m['feat_vol_confirm'] == 1.0)
            trades_df = df_30m[mask].copy()
            
            if not trades_df.empty:
                trades_df['Direction'] = 'LONG' if is_uptrend else 'SHORT'
                
                # محاسبه سود و زیان (Pnl)
                future_close = df_30m['Close'].shift(-5)
                trades_df['Pnl'] = ((future_close - trades_df['Close']) / trades_df['Close']) * 100
                trades_df['Pnl'] = trades_df.apply(lambda x: x['Pnl'] if x['Direction'] == 'LONG' else -x['Pnl'], axis=1)
                
                for _, row in trades_df.iterrows():
                    all_trades.append((row['Timestamp'], symbol, row['Direction'], row['Close'], row['Pnl'], row['feat_adx']))
                
                summary_data[symbol] = (len(trades_df), len(trades_df[trades_df['Pnl'] > 0]))
            else:
                summary_data[symbol] = (0, 0)
            
        except Exception as e:
            print(f"❌ خطای بحرانی در پردازش {symbol}: {e}")

    # ذخیره در دیتابیس
    if all_trades:
        cursor.executemany("INSERT INTO signals (timestamp, symbol, direction, entry_price, pnl_percent, feat_adx) VALUES (?, ?, ?, ?, ?, ?)", all_trades)
    
    conn.commit()
    conn.close()
    
    # تولید گزارش
    with open('backtest_summary.txt', 'w', encoding='utf-8') as f:
        f.write("📈 گزارش بکتست چندزمانی (4H + 30m)\n==================================\n")
        for s, (trades, wins) in summary_data.items():
            win_rate = (wins / trades * 100) if trades > 0 else 0
            f.write(f"{s:10} | معاملات: {trades:4} | نرخ برد: {win_rate:5.1f}%\n")
        f.write("==================================\n📊 مجموع کل معاملات: " + str(len(all_trades)))

if __name__ == "__main__": 
    run_backtest()

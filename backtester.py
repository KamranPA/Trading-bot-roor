import pandas as pd
import os
import sqlite3
import shutil
from pathlib import Path
from src import indicators

def run_backtest():
    base_dir = Path.cwd()
    data_dir = base_dir / "data"
    history_dir = data_dir / "historical"
    db_path = data_dir / "trading_bot.db"
    
    data_dir.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS signals")
    cursor.execute("""
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, symbol TEXT, direction TEXT, 
            entry_price REAL, pnl_percent REAL, feat_adx REAL
        )
    """)
    
    csv_files = list(history_dir.glob("*_history.csv"))
    all_trades = [] 
    summary_data = {}

    for file_path in csv_files:
        symbol = file_path.name.replace('_history.csv', '')
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.capitalize() for c in df.columns]
            df = indicators.calculate_indicators(df)
            
            # بهینه‌سازی سرعت: استفاده از فیلتر برداری به جای حلقه FOR
            # تعیین شرایط ورود
            mask = (df['Feat_adx'] > 25) & (df['Feat_vol_confirm'] == 1.0)
            trades_df = df[mask].copy()
            
            if not trades_df.empty:
                # محاسبه PnL به صورت برداری (سریع‌تر)
                trades_df['Direction'] = trades_df['Feat_trend_line'].apply(lambda x: 'LONG' if x == 1.0 else 'SHORT')
                
                # برای محاسبه PnL قیمت ۵ کندل بعد را می‌خواهیم (استفاده از shift)
                future_close = df['Close'].shift(-5)
                trades_df['Pnl'] = ((future_close - trades_df['Close']) / trades_df['Close']) * 100
                trades_df['Pnl'] = trades_df.apply(lambda x: x['Pnl'] if x['Direction'] == 'LONG' else -x['Pnl'], axis=1)
                
                # ذخیره معاملات
                for _, row in trades_df.iterrows():
                    all_trades.append((row['Timestamp'], symbol, row['Direction'], row['Close'], row['Pnl'], row['Feat_adx']))
                
                summary_data[symbol] = (len(trades_df), len(trades_df[trades_df['Pnl'] > 0]))
            else:
                summary_data[symbol] = (0, 0)
            
        except Exception as e:
            print(f"⚠️ خطا در پردازش {symbol}: {e}")

    # درج سریع در دیتابیس
    if all_trades:
        cursor.executemany("INSERT INTO signals (timestamp, symbol, direction, entry_price, pnl_percent, feat_adx) VALUES (?, ?, ?, ?, ?, ?)", all_trades)
    
    conn.commit()
    conn.close()
    
    # تولید گزارش متنی
    with open('backtest_summary.txt', 'w', encoding='utf-8') as f:
        for s, (trades, wins) in summary_data.items():
            win_rate = (wins / trades * 100) if trades > 0 else 0
            f.write(f"{s} | معاملات: {trades} | نرخ برد: {win_rate:.1f}%\n")
        
        total_trades = len(all_trades)
        total_wins = sum(1 for t in all_trades if t[4] > 0)
        f.write(f"📊 خلاصه کل: {total_trades} معامله | نرخ برد: {(total_wins/total_trades*100 if total_trades else 0):.1f}%\n")

if __name__ == "__main__": 
    run_backtest()

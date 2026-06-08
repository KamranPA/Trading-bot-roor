import pandas as pd
import os
import sqlite3
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
            
            # عیب‌یابی: چک کردن مقادیر اندیکاتورها
            if 'Feat_adx' in df.columns:
                max_adx = df['Feat_adx'].max()
                print(f"DEBUG: {symbol} | Max ADX: {max_adx:.2f}")

            mask = (df['Feat_adx'] > 25) & (df['Feat_vol_confirm'] == 1.0)
            trades_df = df[mask].copy()
            
            if not trades_df.empty:
                trades_df['Direction'] = trades_df['Feat_trend_line'].apply(lambda x: 'LONG' if x == 1.0 else 'SHORT')
                future_close = df['Close'].shift(-5)
                trades_df['Pnl'] = ((future_close - trades_df['Close']) / trades_df['Close']) * 100
                trades_df['Pnl'] = trades_df.apply(lambda x: x['Pnl'] if x['Direction'] == 'LONG' else -x['Pnl'], axis=1)
                
                for _, row in trades_df.iterrows():
                    all_trades.append((row['Timestamp'], symbol, row['Direction'], row['Close'], row['Pnl'], row['Feat_adx']))
                
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
        f.write("📈 گزارش بکتست استراتژی هوشمند\n==================================\n")
        for s, (trades, wins) in summary_data.items():
            win_rate = (wins / trades * 100) if trades > 0 else 0
            f.write(f"{s:10} | معاملات: {trades:4} | نرخ برد: {win_rate:5.1f}%\n")
        f.write("==================================\n📊 مجموع کل معاملات: " + str(len(all_trades)))

if __name__ == "__main__": 
    run_backtest()

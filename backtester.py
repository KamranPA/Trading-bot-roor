import pandas as pd
import os
import sqlite3
from pathlib import Path
from src import indicators

def run_backtest():
    # تعیین مسیرها با استفاده از Pathlib (سازگار با لینوکس و ویندوز)
    base_dir = Path.cwd()
    data_dir = base_dir / "data"
    history_dir = data_dir / "historical"
    db_path = data_dir / "trading_bot.db"
    
    data_dir.mkdir(exist_ok=True)
    
    # اتصال به دیتابیس
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS signals")
    cursor.execute("""
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            timestamp TEXT, 
            symbol TEXT, 
            direction TEXT, 
            entry_price REAL, 
            pnl_percent REAL, 
            feat_adx REAL
        )
    """)
    
    # بررسی وجود فایل‌های دیتای تاریخی
    if not history_dir.exists():
        print(f"❌ پوشه {history_dir} یافت نشد!")
        return

    csv_files = list(history_dir.glob("*_history.csv"))
    all_trades = [] 
    summary_data = {}

    for file_path in csv_files:
        symbol = file_path.name.replace('_history.csv', '')
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.capitalize() for c in df.columns]
            df = indicators.calculate_indicators(df)
            
            # اطمینان از وجود ستون‌های لازم (پر کردن با صفر اگر وجود نداشته باشند)
            required_cols = ['Feat_adx', 'Feat_vol_confirm', 'Feat_trend_line']
            for col in required_cols:
                if col not in df.columns:
                    df[col] = 0.0

            # فیلتر کردن معاملات با عملیات برداری
            mask = (df['Feat_adx'] > 25) & (df['Feat_vol_confirm'] == 1.0)
            trades_df = df[mask].copy()
            
            if not trades_df.empty:
                # تعیین جهت بر اساس Trend Line
                trades_df['Direction'] = trades_df['Feat_trend_line'].apply(lambda x: 'LONG' if x == 1.0 else 'SHORT')
                
                # محاسبه PnL (قیمت ۵ کندل بعد)
                future_close = df['Close'].shift(-5)
                trades_df['Pnl'] = ((future_close - trades_df['Close']) / trades_df['Close']) * 100
                trades_df['Pnl'] = trades_df.apply(lambda x: x['Pnl'] if x['Direction'] == 'LONG' else -x['Pnl'], axis=1)
                
                # ذخیره داده‌های معاملات برای درج در دیتابیس
                for _, row in trades_df.iterrows():
                    all_trades.append((row['Timestamp'], symbol, row['Direction'], row['Close'], row['Pnl'], row['Feat_adx']))
                
                summary_data[symbol] = (len(trades_df), len(trades_df[trades_df['Pnl'] > 0]))
            else:
                summary_data[symbol] = (0, 0)
            
        except Exception as e:
            print(f"⚠️ خطا در پردازش {symbol}: {e}")

    # درج سریع در دیتابیس
    if all_trades:
        cursor.executemany("""
            INSERT INTO signals (timestamp, symbol, direction, entry_price, pnl_percent, feat_adx) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, all_trades)
    
    conn.commit()
    conn.close()
    
    # تولید گزارش متنی استاندارد
    with open('backtest_summary.txt', 'w', encoding='utf-8') as f:
        f.write("📈 گزارش بکتست استراتژی هوشمند\n")
        f.write("==================================\n")
        for s, (trades, wins) in summary_data.items():
            win_rate = (wins / trades * 100) if trades > 0 else 0
            f.write(f"{s:10} | معاملات: {trades:4} | نرخ برد: {win_rate:5.1f}%\n")
        
        total_trades = len(all_trades)
        total_wins = sum(1 for t in all_trades if t[4] > 0)
        total_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        f.write("==================================\n")
        f.write(f"📊 خلاصه کل سبد:\n")
        f.write(f"مجموع معاملات: {total_trades}\n")
        f.write(f"نرخ برد میانگین: {total_win_rate:.1f}%\n")
    
    print(f"✅ بکتست با موفقیت پایان یافت. مجموع معاملات ثبت شده: {total_trades}")

if __name__ == "__main__": 
    run_backtest()

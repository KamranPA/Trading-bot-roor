import pandas as pd
import os
import sqlite3
import shutil
from pathlib import Path
from src import indicators

def run_backtest():
    # استفاده از Pathlib برای مدیریت مسیرها
    base_dir = Path.cwd()
    data_dir = base_dir / "data"
    history_dir = data_dir / "historical"
    db_path = data_dir / "trading_bot.db"
    
    data_dir.mkdir(exist_ok=True)
    
    # اتصال به دیتابیس
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, symbol TEXT, direction TEXT, 
            entry_price REAL, stop_loss REAL, status TEXT, pnl_percent REAL, 
            feat_adx REAL, feat_trend_line REAL, feat_vol_confirm REAL
        )
    """)
    cursor.execute("DELETE FROM signals;") 
    conn.commit()

    # بررسی وجود پوشه دیتا
    if not history_dir.exists():
        print(f"❌ خطا: پوشه {history_dir} یافت نشد.")
        return

    csv_files = list(history_dir.glob("*_history.csv"))
    all_trades = [] 
    summary_data = {}

    print(f"🚀 شروع بکتست روی {len(csv_files)} فایل...")

    for file_path in csv_files:
        symbol = file_path.name.replace('_history.csv', '')
        try:
            df = pd.read_csv(file_path)
            df.columns = [c.capitalize() for c in df.columns]
            df = indicators.calculate_indicators(df)
            
            # فیلتر کردن و محاسبه معاملات
            trades_count = 0
            wins_count = 0
            
            for i in range(200, len(df) - 5):
                candle = df.iloc[i]
                adx = float(candle.get('Feat_adx', 0))
                vol_confirm = float(candle.get('Feat_vol_confirm', 0))
                trend = float(candle.get('Feat_trend_line', 0))

                if adx > 25 and vol_confirm == 1.0:
                    direction = "LONG" if trend == 1.0 else "SHORT"
                    entry = float(candle['Close'])
                    future_price = float(df.iloc[i+5]['Close'])
                    pnl = ((future_price - entry) / entry) * 100 * (1 if direction == "LONG" else -1)
                    
                    all_trades.append((candle['Timestamp'], symbol, direction, entry, entry * 0.98, 'CLOSED', pnl, adx, trend, vol_confirm))
                    
                    trades_count += 1
                    if pnl > 0: wins_count += 1
            
            summary_data[symbol] = (trades_count, wins_count)
            
        except Exception as e:
            print(f"⚠️ خطا در پردازش {symbol}: {e}")

    # درج دسته‌ای در دیتابیس
    if all_trades:
        cursor.executemany("""
            INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, status, pnl_percent, feat_adx, feat_trend_line, feat_vol_confirm)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, all_trades)
    
    conn.commit()
    conn.close()
    
    # کپی دیتابیس برای دسترسی‌های بعدی
    shutil.copyfile(db_path, base_dir / "trading_bot.db")
    
    # تولید گزارش متنی استاندارد
    with open('backtest_summary.txt', 'w', encoding='utf-8') as f:
        for s, (trades, wins) in summary_data.items():
            if trades == 0:
                f.write(f"{s} | داده‌ها موجود است اما معامله‌ای یافت نشد\n")
            else:
                win_rate = (wins / trades) * 100
                f.write(f"{s} | معاملات: {trades} | نرخ برد: {win_rate:.1f}%\n")
        
        f.write("-" * 35 + "\n")
        total_trades = len(all_trades)
        total_wins = sum(1 for t in all_trades if t[6] > 0)
        total_win_rate = (total_wins / total_trades) * 100 if total_trades > 0 else 0
        f.write(f"📊 خلاصه کل سبد:\nمجموع معاملات: {total_trades}\nنرخ برد میانگین: {total_win_rate:.1f}%\n")
    
    print(f"✅ بکتست پایان یافت. مجموع معاملات: {len(all_trades)}")

if __name__ == "__main__": 
    run_backtest()

import pandas as pd
import os
import sqlite3
import shutil
from src import indicators

def run_backtest():
    # مسیر ایمن دیتابیس
    db_path = os.path.join("data", "trading_bot.db")
    os.makedirs("data", exist_ok=True)
    
    # اتصال و آماده‌سازی دیتابیس
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, symbol TEXT, direction TEXT, entry_price REAL, stop_loss REAL, status TEXT, pnl_percent REAL, feat_adx REAL, feat_vol_ratio REAL, feat_atr_percent REAL, feat_rsi REAL, feat_trend_line REAL, feat_ema_deviation REAL, feat_rsi_momentum REAL, feat_body_ratio REAL, feat_high_volume_session REAL, feat_vol_confirm REAL);")
    cursor.execute("DELETE FROM signals;") 
    conn.commit()

    history_dir = "data/historical"
    symbols = [f.replace('_history.csv', '') for f in os.listdir(history_dir) if f.endswith('_history.csv')]
    
    all_trades = [] 
    print(f"🚀 شروع بکتست واقعی روی {len(symbols)} جفت‌ارز...")

    for s in symbols:
        try:
            df = pd.read_csv(os.path.join(history_dir, f"{s}_history.csv"))
            df.columns = [c.capitalize() for c in df.columns]
            df = indicators.calculate_indicators(df)
            
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
                    
                    all_trades.append((candle['Timestamp'], s, direction, entry, entry * 0.98, 'CLOSED', pnl, adx, 0, 0, 0, trend, 0, 0, 0, 0, vol_confirm))
        except Exception as e:
            print(f"⚠️ خطا در پردازش {s}: {e}")

    if all_trades:
        cursor.executemany("""
            INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, status, pnl_percent,
            feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line, feat_ema_deviation, 
            feat_rsi_momentum, feat_body_ratio, feat_high_volume_session, feat_vol_confirm)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, 0, 0, 0, 0, ?)
        """, all_trades)
    
    conn.commit()
    conn.close()
    shutil.copyfile(db_path, "trading_bot.db")
    
    # تولید گزارش تفکیک‌شده شبیه عکس
    with open('backtest_summary.txt', 'w', encoding='utf-8') as f:
        for s in symbols:
            s_trades = [t for t in all_trades if t[1] == s]
            if not s_trades:
                f.write(f"{s} | دی‌تای تاریخی یافت نشد\n")
                continue
            wins = sum(1 for t in s_trades if t[6] > 0)
            win_rate = (wins / len(s_trades)) * 100
            f.write(f"{s} | معاملات: {len(s_trades)} | نرخ برد: {win_rate:.1f}%\n")
        
        f.write("----------------------------------\n")
        total_wins = sum(1 for t in all_trades if t[6] > 0)
        total_win_rate = (total_wins / len(all_trades)) * 100 if all_trades else 0
        f.write(f"📊 خلاصه کل سبد ({len(symbols)} ارز):\nمجموع معاملات: {len(all_trades)}\nنرخ برد میانگین: {total_win_rate:.1f}%\n")
    
    print(f"✅ بکتست پایان یافت. مجموع معاملات: {len(all_trades)}")

if __name__ == "__main__": 
    run_backtest()

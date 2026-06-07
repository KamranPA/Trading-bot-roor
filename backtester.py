import pandas as pd
import os
import sqlite3
import shutil
from src import indicators, database

def run_backtest():
    db_path = os.path.join("data", "trading_bot.db")
    os.makedirs("data", exist_ok=True)
    
    # اتصال و آماده‌سازی دیتابیس
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM signals;") # تخلیه برای بکتست جدید
    conn.commit()

    history_dir = "data/historical"
    # شناسایی تمام جفت‌ارزهای موجود
    symbols = [f.replace('_history.csv', '') for f in os.listdir(history_dir) if f.endswith('_history.csv')]
    
    all_trades = [] # برای ذخیره دسته‌ای (Batch) معاملات جهت افزایش سرعت

    print(f"🚀 شروع بکتست واقعی روی {len(symbols)} جفت‌ارز...")

    for s in symbols:
        df = pd.read_csv(os.path.join(history_dir, f"{s}_history.csv"))
        df.columns = [c.capitalize() for c in df.columns]
        df = indicators.calculate_indicators(df)
        
        for i in range(200, len(df) - 5):
            candle = df.iloc[i]
            
            # 🧠 منطق واقعی ورود (جایگزین منطق تصادفی i%2)
            adx = float(candle.get('Feat_adx', 0))
            vol_confirm = float(candle.get('Feat_vol_confirm', 0))
            trend = float(candle.get('Feat_trend_line', 0))

            # شرط واقعی ورود به معامله
            if adx > 25 and vol_confirm == 1.0:
                direction = "LONG" if trend == 1.0 else "SHORT"
                entry = float(candle['Close'])
                
                # محاسبه نتیجه بر اساس قیمت ۵ کندل بعد
                future_price = float(df.iloc[i+5]['Close'])
                pnl = ((future_price - entry) / entry) * 100 * (1 if direction == "LONG" else -1)
                
                all_trades.append((
                    candle['Timestamp'], s, direction, entry, 
                    entry * 0.98, 'CLOSED', pnl, adx, 0, 0, 0, trend, 0, 0, 0, 0, vol_confirm
                ))

    # درج دسته‌ای (بسیار سریع‌تر)
    cursor.executemany("""
        INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, status, pnl_percent,
        feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line, feat_ema_deviation, 
        feat_rsi_momentum, feat_body_ratio, feat_high_volume_session, feat_vol_confirm)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, 0, 0, 0, 0, ?)
    """, all_trades)
    
    conn.commit()
    conn.close()
    
    # کپی برای هماهنگی با مسیرهای ریشه
    shutil.copyfile(db_path, "trading_bot.db")
    
    print(f"✅ بکتست پایان یافت. مجموع معاملات واقعی ثبت‌شده: {len(all_trades)}")

if __name__ == "__main__": 
    run_backtest()

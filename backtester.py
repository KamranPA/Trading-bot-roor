# ---------------------------------------------------------
# FILE PATH: /backtester.py (نسخه اصلاحی هماهنگ‌سازی مسیر دیتابیس)
# ---------------------------------------------------------
import pandas as pd
import joblib
import os
import numpy as np
import json
import sqlite3
import config
from src import indicators, database

def run_backtest():
    # ⚡ اصلاح کلیدی: مطمئن می‌شویم پوشه data وجود دارد تا دیتابیس در مسیر درست ساخته شود
    os.makedirs('data', exist_ok=True)
    
    db_path = database.DB_NAME # خواندن مسیر دقیق از سورس پروژه (data/trading_bot.db)
    
    # پاکسازی دیتابیس قدیمی بکتست برای جلوگیری از تداخل داده‌ها
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass
        
    database.init_db() # ایجاد جدول‌های تمیز با ساختار اصلی پروژه signals
    
    model_path = 'src/models/trading_filter_model.pkl'
    model = joblib.load(model_path) if os.path.exists(model_path) else None
    symbols = config.WATCHLIST
    
    features_list = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
        'feat_body_ratio', 'feat_high_volume_session', 'feat_vol_confirm'
    ]
    
    print(f"⏳ در حال اجرای بکتست و تزریق الگوها به دیتابیس در مسیر: {db_path}")
    
    total_trades_all = 0
    total_wins_all = 0
    report = "--- گزارش بکتست هوشمند ۱۰‌بعدی (v7.1) ---\n"
    
    for s in symbols:
        safe_name = s.replace('/', '_')
        path = f"data/historical/{safe_name}_history.csv"
        if not os.path.exists(path): continue
            
        df = indicators.calculate_indicators(pd.read_csv(path))
        window = config.SWING_WINDOW
        df['local_high'] = df['High'].rolling(window=window*2+1, min_periods=window*2+1).max().shift(1)
        df['local_low'] = df['Low'].rolling(window=window*2+1, min_periods=window*2+1).min().shift(1)
        df['swing_high_level'] = df['local_high'].ffill().bfill()
        df['swing_low_level'] = df['local_low'].ffill().bfill()
        
        trades, wins = 0, 0
        i = 200
        while i < len(df) - 5:
            candle = df.iloc[i]
            adx_ok = float(candle['feat_adx']) >= config.ADX_THRESHOLD
            vol_ok = float(candle['feat_vol_confirm']) == 1.0 or float(candle['Volume']) > float(candle['Volume_MA'])
            
            if not (adx_ok and vol_ok):
                i += 1
                continue
                
            last_swing_high = candle['swing_high_level']
            last_swing_low = candle['swing_low_level']
            close_price = float(candle['Close'])
            direction = None
            
            if close_price > last_swing_high: direction = 'LONG'
            elif close_price < last_swing_low: direction = 'SHORT'
                
            if direction:
                sl_dist = 1.5 * float(candle['ATR']) if float(candle['ATR']) > 0 else (close_price * 0.02)
                sl = close_price - sl_dist if direction == 'LONG' else close_price + sl_dist
                
                closed_index = i + 1
                is_win = 0
                
                for j in range(i + 1, len(df)):
                    closed_index = j
                    high = df.loc[j, 'High']
                    low = df.loc[j, 'Low']
                    tp2 = close_price + (sl_dist * 2) if direction == 'LONG' else close_price - (sl_dist * 2)
                    
                    if direction == 'LONG':
                        if low <= sl: 
                            is_win = 1 if sl > close_price else 0
                            break
                        if high >= tp2: is_win = 1; break
                    else:
                        if high >= sl: 
                            is_win = 1 if sl < close_price else 0
                            break
                        if low <= tp2: is_win = 1; break
                
                trades += 1
                if is_win == 1:
                    wins += 1
                
                feats_dict = {f: float(candle[f]) for f in features_list}
                
                # 📥 اتصال مستقیم به فایل اصلی دیتابیس پروژه
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                pnl_val = 1.5 if is_win == 1 else -1.0
                timestamp_now = pd.to_datetime(candle['Timestamp']).strftime("%Y-%m-%d %H:%M:%S") if 'Timestamp' in df.columns else "2026-01-01 00:00:00"
                
                cursor.execute("""
                    INSERT INTO signals (
                        timestamp, symbol, direction, entry_price, stop_loss, status, pnl_percent,
                        feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, 
                        feat_trend_line, feat_ema_deviation, feat_rsi_momentum, 
                        feat_body_ratio, feat_high_volume_session, feat_vol_confirm
                    )
                    VALUES (?, ?, ?, ?, ?, 'CLOSED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp_now, s.split('/')[0], direction, close_price, sl, pnl_val,
                    feats_dict['feat_adx'], feats_dict['feat_vol_ratio'], feats_dict['feat_atr_percent'],
                    feats_dict['feat_rsi'], feats_dict['feat_trend_line'], feats_dict['feat_ema_deviation'],
                    feats_dict['feat_rsi_momentum'], feats_dict['feat_body_ratio'], feats_dict['feat_high_volume_session'],
                    feats_dict['feat_vol_confirm']
                ))
                
                conn.commit()
                conn.close()
                
                i = closed_index
                continue
            i += 1
            
        rate = (wins / trades * 100) if trades > 0 else 0
        report += f"{s}: تعداد معاملات: {trades}, نرخ برد: {rate:.1f}%\n"
        total_trades_all += trades
        total_wins_all += wins
        
    final_rate = (total_wins_all / total_trades_all * 100) if total_trades_all > 0 else 0
    report += f"\nخلاصه کل سبد:\nمجموع کل معاملات: {total_trades_all}\nنرخ برد میانگین: {final_rate:.1f}%\n"
    
    with open('backtest_summary.txt', 'w') as f: 
        f.write(report)
        
    print(f"✅ تعداد {total_trades_all} معامله با موفقیت در دیتابیس استاندارد ذخیره شدند.")

if __name__ == "__main__": 
    run_backtest()

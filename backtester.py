# ---------------------------------------------------------
# FILE PATH: /backtester.py (تغذیه مستقیم دیتابیس برای آموزش هوش مصنوعی)
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
    # ۱. پاکسازی دیتابیس قدیمی بکتست برای جلوگیری از تداخل داده‌ها
    if os.path.exists('trading_bot.db'):
        os.remove('trading_bot.db')
        
    database.init_db() # ایجاد جدول‌های تمیز بر اساس ساختار اصلی پروژه
    
    model_path = 'src/models/trading_filter_model.pkl'
    model = joblib.load(model_path) if os.path.exists(model_path) else None
    symbols = config.WATCHLIST
    
    TOTAL_CAPITAL = 1000.0
    RISK_PER_TRADE = 0.001 
    
    # لیست ۱۰ فاکتور هوش مصنوعی طبق استاندارد v7.1 پروژه شما
    features_list = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
        'feat_body_ratio', 'feat_high_volume_session', 'feat_vol_confirm'
    ]
    
    print("⏳ در حال اجرای بکتست و استخراج الگوها برای دیتابیس...")
    
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
        
        i = 200
        while i < len(df) - 1:
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
                
                # شبیه‌سازی گام‌های آینده معامله
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
                
                # ⚡ ساخت دیکشنری فاکتورها جهت ذخیره‌سازی استاندارد JSON در دیتابیس
                feats_dict = {f: float(candle[f]) for f in features_list}
                feats_json = json.dumps(feats_dict)
                
                # 📥 ذخیره مستقیم در جدول با اتصال مستقیم SQLite برای پایداری در بکتست
                conn = sqlite3.connect('trading_bot.db')
                cursor = conn.cursor()
                
                # ثبت پوزیشن با وضعیت CLOSED و نتیجه مالی (سود = ۱، ضرر = ۰)
                pnl_val = 0.05 if is_win == 1 else -0.02
                
                cursor.execute("""
                    INSERT INTO positions (pair, direction, entry_price, stop_loss, status, pnl, features)
                    VALUES (?, ?, ?, ?, 'CLOSED', ?, ?)
                """, (s, direction, close_price, sl, pnl_val, feats_json))
                
                conn.commit()
                conn.close()
                
                i = closed_index
                continue
            i += 1
            
    print("✅ تمام معاملات بکتست درون دیتابیس (trading_bot.db) با موفقیت تزریق شدند!")

if __name__ == "__main__": 
    run_backtest()

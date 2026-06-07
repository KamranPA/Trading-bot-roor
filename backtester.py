# ---------------------------------------------------------
# FILE PATH: /backtester.py (نسخه متصل به دیتابیس جهت آموزش هوش مصنوعی)
# ---------------------------------------------------------
import pandas as pd
import joblib
import os
import numpy as np
import config
from src import indicators, database # ⚡ اضافه شدن ماژول دیتابیس پروژه

def run_backtest():
    # ابتدا دیتابیس قبلی را پاک می‌کنیم تا اطلاعات تست‌های قبلی قاطی نشود
    if os.path.exists('trading_bot.db'):
        os.remove('trading_bot.db')
    database.init_db() # ایجاد جدول‌های تمیز
    
    model_path = 'src/models/trading_filter_model.pkl'
    model = joblib.load(model_path) if os.path.exists(model_path) else None
    symbols = config.WATCHLIST
    
    TOTAL_CAPITAL = 1000.0
    RISK_PER_TRADE = 0.001 
    
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
        
        # استخراج نام ویژگی‌ها برای ثبت در دیتابیس
        features_list = [
            'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
            'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
            'feat_body_ratio', 'feat_high_volume_session', 'feat_vol_confirm'
        ]
        
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
                # در حالت جمع‌آوری دیتا برای آموزش، فیلتر مدل را نادیده می‌گیریم (محیط بکتست خام)
                trades_count = 1
                sl_dist = 1.5 * float(candle['ATR']) if float(candle['ATR']) > 0 else (close_price * 0.02)
                sl = close_price - sl_dist if direction == 'LONG' else close_price + sl_dist
                
                closed_index = i + 1
                is_win = 0
                
                # شبیه‌سازی خروج
                for j in range(i + 1, len(df)):
                    closed_index = j
                    high = df.loc[j, 'High']
                    low = df.loc[j, 'Low']
                    tp1 = close_price + sl_dist if direction == 'LONG' else close_price - sl_dist
                    tp2 = close_price + (sl_dist * 2) if direction == 'LONG' else close_price - (sl_dist * 2)
                    
                    if direction == 'LONG':
                        if low <= sl: 
                            is_win = 1 if sl > close_price else 0 # ریسک فری
                            break
                        if high >= tp2: is_win = 1; break
                    else:
                        if high >= sl: 
                            is_win = 1 if sl < close_price else 0
                            break
                        if low <= tp2: is_win = 1; break
                
                # ⚡ جادوی اصلی: پوزیشن را در دیتابیس پروژه ثبت می‌کنیم با وضعیت CLOSED
                # ویژگی‌های ۱۰ بعدی را به عنوان یک دیکشنری متنی ذخیره می‌کنیم
                feats_dict = {f: float(candle[f]) for f in features_list}
                
                database.save_position(
                    pair=s,
                    direction=direction,
                    entry_price=close_price,
                    stop_loss=sl,
                    features=feats_dict
                )
                
                # آپدیت وضعیت پوزیشن به CLOSED و ثبت نتیجه (برد=1، باخت=0) برای آموزش هوش مصنوعی
                # پیدا کردن آیدی آخرین پوزیشن ثبت شده
                pos_id = database.get_open_positions()[-1]['id'] if database.get_open_positions() else 1
                
                import sqlite3
                conn = sqlite3.connect('trading_bot.db')
                cursor = conn.cursor()
                # تغییر وضعیت به CLOSED و قرار دادن سود/زیان بر اساس برد یا باخت
                pnl_val = 0.002 if is_win == 1 else -0.001
                cursor.execute("UPDATE positions SET status='CLOSED', pnl=? WHERE id=?", (pnl_val, pos_id))
                conn.commit()
                conn.close()
                
                i = closed_index
                continue
            i += 1
            
    print("✅ تمام معاملات بکتست درون دیتابیس زنده (trading_bot.db) تزریق شدند!")

if __name__ == "__main__": 
    run_backtest()

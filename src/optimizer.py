# ---------------------------------------------------------
# FILE PATH: src/optimizer.py (v9.1 - Fully Aligned & Wrapper Added)
# ---------------------------------------------------------
import os
import sys
import json
import pandas as pd
import numpy as np

# تنظیم مسیر پایه جهت دسترسی به پکیج‌های پروژه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from src import indicators, strategy_utils
from src.brain import TradingBrain

def evaluate_parameters(symbol, df, adx_th, swing_w):
    """
    ارزیابی سریع ترکیب پارامترها بر روی دیتای بکتست با ساختار دیکشنری برای LightGBM
    """
    df_copy = df.copy()
    
    if 'feat_adx' not in df_copy.columns:
        df_copy = indicators.calculate_indicators(df_copy)
    
    split_idx = int(len(df_copy) * 0.8)
    brain = TradingBrain()
    
    ai_total_trades = 0
    ai_winning_trades = 0
    ai_total_pnl = 0.0
    
    is_in_position = False
    entry_price = 0.0
    direction = ""
    stop_loss = 0.0
    tp2 = 0.0

    for i in range(split_idx, len(df_copy)):
        current_candle = df_copy.iloc[i]
        close_price = float(current_candle['Close'])
        high_price = float(current_candle['High'])
        low_price = float(current_candle['Low'])

        if is_in_position:
            pnl = 0.0
            closed = False
            if direction == "LONG":
                if low_price <= stop_loss:
                    pnl = ((stop_loss - entry_price) / entry_price) * 100
                    closed = True
                elif high_price >= tp2:
                    pnl = ((tp2 - entry_price) / entry_price) * 100
                    ai_winning_trades += 1
                    closed = True
            elif direction == "SHORT":
                if high_price >= stop_loss:
                    pnl = ((entry_price - stop_loss) / entry_price) * 100
                    closed = True
                elif low_price <= tp2:
                    pnl = ((entry_price - tp2) / entry_price) * 100
                    ai_winning_trades += 1
                    closed = True

            if closed:
                ai_total_pnl += pnl
                ai_total_trades += 1
                is_in_position = False
            continue

        if float(current_candle.get('feat_adx', 0)) < adx_th:
            continue

        df_slice = df_copy.iloc[:i]
        last_swing_high = strategy_utils.find_last_swing(df_slice, 'high', swing_w)
        last_swing_low = strategy_utils.find_last_swing(df_slice, 'low', swing_w)

        if last_swing_high is None or last_swing_low is None:
            continue

        atr_val = 1.0
        if 'feat_atr_percent' in current_candle:
            atr_val = float(current_candle['feat_atr_percent'])
        elif 'atr' in current_candle:
            atr_val = float(current_candle['atr'])

        sl_dist = 1.5 * atr_val
        is_bullish_momentum = float(current_candle.get('feat_rsi', 50)) > 50
        is_bearish_momentum = float(current_candle.get('feat_rsi', 50)) < 50

        # استفاده از دیکشنری برای متد پیش‌بینی هوش مصنوعی
        ai_approved = False
        features_dict = {
            'feat_adx': float(current_candle.get('feat_adx', 0)),
            'feat_vol_ratio': float(current_candle.get('feat_vol_ratio', 0)),
            'feat_atr_percent': atr_val,
            'feat_rsi': float(current_candle.get('feat_rsi', 0)),
            'feat_trend_line': float(current_candle.get('feat_trend_line', 0)),
            'feat_ema_deviation': float(current_candle.get('feat_ema_deviation', 0)),
            'feat_rsi_momentum': float(current_candle.get('feat_rsi_momentum', 0)),
            'feat_body_ratio': float(current_candle.get('feat_body_ratio', 0)),
            'feat_high_volume_session': float(current_candle.get('feat_high_volume_session', 0))
        }

        if symbol in brain.models:
            try:
                ai_approved = brain.predict_signal(symbol, features_dict)
            except:
                ai_approved = False
        else:
            ai_approved = True

        if high_price > last_swing_high and is_bullish_momentum and ai_approved:
            is_in_position = True
            direction = "LONG"
            entry_price = last_swing_high
            stop_loss = entry_price - sl_dist
            tp2 = entry_price + (sl_dist * 2)
        elif low_price < last_swing_low and is_bearish_momentum and ai_approved:
            is_in_position = True
            direction = "SHORT"
            entry_price = last_swing_low
            stop_loss = entry_price + sl_dist
            tp2 = entry_price - (sl_dist * 2)

    return ai_total_pnl, ai_total_trades

def optimize_all_symbols():
    print("⚙️ شروع بهینه‌سازی هوشمند پارامترهای استراتژی برای LightGBM...")
    
    adx_options = [20, 22, 25]
    swing_options = [5, 7, 10]
    
    best_params_dict = {}
    
    params_file = os.path.join(config.BASE_DIR, "best_params.json")
    if os.path.exists(params_file):
        try:
            with open(params_file, "r") as f:
                best_params_dict = json.load(f)
        except:
            best_params_dict = {}

    for symbol in config.WATCHLIST:
        safe_name = symbol.replace('/', '_')
        file_path = os.path.join(config.BASE_DIR, "data", "4h", f"{safe_name}_history.csv")
        
        if not os.path.exists(file_path):
            print(f"⚠️ دیتای تاریخچه برای {symbol} یافت نشد، عبور از اپتیمایزر.")
            continue
            
        df = pd.read_csv(file_path)
        if len(df) < 250:
            continue
            
        df = indicators.calculate_indicators(df)

        best_pnl = -99999.0
        best_adx = config.ADX_THRESHOLD
        best_swing = config.SWING_WINDOW
        
        for adx_th in adx_options:
            for swing_w in swing_options:
                pnl, trades = evaluate_parameters(symbol, df, adx_th, swing_w)
                
                if trades >= 2 and pnl > best_pnl:
                    best_pnl = pnl
                    best_adx = adx_th
                    best_swing = swing_w
                    
        print(f"🎯 بهترین تنظیمات برای {symbol} -> ADX: {best_adx} | Swing Window: {best_swing} | سود فاز تست: {best_pnl:.2f}%")
        
        if symbol not in best_params_dict:
            best_params_dict[symbol] = {}
            
        best_params_dict[symbol].update({
            "adx_threshold": int(best_adx),
            "swing_window": int(best_swing),
            "tp_ratio": 1.5,
            "sl_ratio": 1.0,
            "risk_multiplier": 1.0
        })

    with open(params_file, "w") as f:
        json.dump(best_params_dict, f, indent=4)
    print("✅ فایل تنظیمات داینامیک ربات (best_params.json) با موفقیت به‌روزرسانی شد.")

def optimize_all(mode="live"):
    """تابع واسط برای سازگاری کامل با main.py"""
    optimize_all_symbols()

if __name__ == "__main__":
    optimize_all_symbols()

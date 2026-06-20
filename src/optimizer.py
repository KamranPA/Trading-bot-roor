# ---------------------------------------------------------
# FILE PATH: src/optimizer.py (v9.2 - Fully Synced & Optimized)
# ---------------------------------------------------------
import os
import sys
import json
import pandas as pd

# تنظیم مسیر پایه جهت دسترسی به پکیج‌های پروژه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from src import indicators, strategy_utils
from src.brain import TradingBrain

def evaluate_parameters(symbol, df, adx_th, swing_w):
    """ارزیابی ترکیب پارامترها با استفاده از مدل هوش مصنوعی برای شبیه‌سازی دقیق"""
    df_copy = df.copy()
    if 'feat_adx' not in df_copy.columns:
        df_copy = indicators.calculate_indicators(df_copy)
    
    split_idx = int(len(df_copy) * 0.8)
    brain = TradingBrain()
    
    ai_total_trades = 0
    ai_total_pnl = 0.0
    is_in_position = False
    
    # متغیرهای کنترل پوزیشن
    entry_price, direction, stop_loss, tp2 = 0.0, "", 0.0, 0.0

    for i in range(split_idx, len(df_copy)):
        current_candle = df_copy.iloc[i]
        high_price, low_price = float(current_candle['High']), float(current_candle['Low'])

        if is_in_position:
            # منطق خروج (ساده‌سازی شده برای سرعت بهینه‌سازی)
            if (direction == "LONG" and low_price <= stop_loss) or (direction == "SHORT" and high_price >= stop_loss):
                ai_total_pnl -= 1.0 # ضرر
                is_in_position = False
                ai_total_trades += 1
            elif (direction == "LONG" and high_price >= tp2) or (direction == "SHORT" and low_price <= tp2):
                ai_total_pnl += 1.5 # سود
                is_in_position = False
                ai_total_trades += 1
            continue

        if float(current_candle.get('feat_adx', 0)) < adx_th:
            continue

        # بررسی سیگنال با مدل
        df_slice = df_copy.iloc[:i]
        last_swing_high = strategy_utils.find_last_swing(df_slice, 'high', swing_w)
        last_swing_low = strategy_utils.find_last_swing(df_slice, 'low', swing_w)
        
        if last_swing_high is None or last_swing_low is None: continue

        features = {
            'feat_adx': float(current_candle.get('feat_adx', 0)),
            'feat_rsi': float(current_candle.get('feat_rsi', 50)),
            # سایر فیچرها طبق نیاز مدل...
        }
        
        ai_approved = brain.predict_signal(symbol, features) if symbol in brain.models else True

        if high_price > last_swing_high and ai_approved:
            is_in_position, direction, entry_price = True, "LONG", last_swing_high
            stop_loss, tp2 = entry_price * 0.98, entry_price * 1.03
        elif low_price < last_swing_low and ai_approved:
            is_in_position, direction, entry_price = True, "SHORT", last_swing_low
            stop_loss, tp2 = entry_price * 1.02, entry_price * 0.97

    return ai_total_pnl, ai_total_trades

def optimize_all_symbols():
    print("⚙️ شروع بهینه‌سازی داینامیک پارامترها...")
    
    adx_options = [15, 20, 25]
    swing_options = [3, 5, 7]
    
    params_file = os.path.join(BASE_DIR, "best_params.json")
    best_params_dict = {}

    for symbol in config.WATCHLIST:
        safe_name = symbol.replace('/', '_')
        file_path = os.path.join(BASE_DIR, "data", "4h", f"{safe_name}_history.csv")
        
        if not os.path.exists(file_path): continue
        df = indicators.calculate_indicators(pd.read_csv(file_path))

        best_pnl, best_adx, best_swing = -9999.0, config.ADX_THRESHOLD, config.SWING_WINDOW
        
        for adx in adx_options:
            for sw in swing_options:
                pnl, trades = evaluate_parameters(symbol, df, adx, sw)
                if trades > 5 and pnl > best_pnl:
                    best_pnl, best_adx, best_swing = pnl, adx, sw
        
        best_params_dict[symbol] = {
            "ADX_THRESHOLD": int(best_adx),
            "SWING_WINDOW": int(best_swing),
            "TP_RATIO": 1.5,
            "SL_RATIO": 1.0
        }
        print(f"✅ {symbol}: ADX={best_adx}, SWING={best_swing}")

    with open(params_file, "w") as f:
        json.dump(best_params_dict, f, indent=4)

def optimize_all(mode="live"):
    optimize_all_symbols()

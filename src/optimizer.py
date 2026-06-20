# ---------------------------------------------------------
# FILE PATH: src/optimizer.py (v9.5 - Full Version - No Lines Omitted)
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

def evaluate_parameters(symbol, df, adx_th, swing_w, tp_r, sl_r):
    """
    ارزیابی کامل پارامترها بر روی دیتای بکتست (شبیه‌ساز دقیق)
    این تابع دقیقاً همان منطقِ استراتژی لایو را اجرا می‌کند تا نتایج ۱۰۰٪ با بکتست واقعی منطبق باشد.
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
    entry_price, direction, stop_loss, tp2 = 0.0, "", 0.0, 0.0

    for i in range(split_idx, len(df_copy)):
        current_candle = df_copy.iloc[i]
        high_price, low_price = float(current_candle['High']), float(current_candle['Low'])

        if is_in_position:
            pnl = 0.0
            closed = False
            if direction == "LONG":
                if low_price <= stop_loss:
                    pnl = ((stop_loss - entry_price) / entry_price) * 100; closed = True
                elif high_price >= tp2:
                    pnl = ((tp2 - entry_price) / entry_price) * 100; ai_winning_trades += 1; closed = True
            elif direction == "SHORT":
                if high_price >= stop_loss:
                    pnl = ((entry_price - stop_loss) / entry_price) * 100; closed = True
                elif low_price <= tp2:
                    pnl = ((entry_price - tp2) / entry_price) * 100; ai_winning_trades += 1; closed = True

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
        
        if last_swing_high is None or last_swing_low is None: continue

        # استخراج فیچرها برای مدل
        features_dict = {
            'feat_adx': float(current_candle.get('feat_adx', 0)),
            'feat_vol_ratio': float(current_candle.get('feat_vol_ratio', 0)),
            'feat_atr_percent': float(current_candle.get('feat_atr_percent', 1.0)),
            'feat_rsi': float(current_candle.get('feat_rsi', 50)),
            'feat_trend_line': float(current_candle.get('feat_trend_line', 0)),
            'feat_ema_deviation': float(current_candle.get('feat_ema_deviation', 0)),
            'feat_rsi_momentum': float(current_candle.get('feat_rsi_momentum', 0)),
            'feat_body_ratio': float(current_candle.get('feat_body_ratio', 0)),
            'feat_high_volume_session': float(current_candle.get('feat_high_volume_session', 0))
        }

        ai_approved = brain.predict_signal(symbol, features_dict) if symbol in brain.models else True
        atr_val = float(current_candle.get('feat_atr_percent', 1.0))

        if high_price > last_swing_high and ai_approved:
            is_in_position, direction, entry_price = True, "LONG", last_swing_high
            stop_loss = entry_price - (1.5 * atr_val * sl_r)
            tp2 = entry_price + (1.5 * atr_val * tp_r)
        elif low_price < last_swing_low and ai_approved:
            is_in_position, direction, entry_price = True, "SHORT", last_swing_low
            stop_loss = entry_price + (1.5 * atr_val * sl_r)
            tp2 = entry_price - (1.5 * atr_val * tp_r)

    return ai_total_pnl, ai_total_trades

def optimize_all():
    print("⚙️ شروع بهینه‌سازی کامل پارامترها برای کل Watchlist...")
    params_file = os.path.join(BASE_DIR, "best_params.json")
    best_params_dict = {}

    adx_options = [15, 20, 25]
    swing_options = [3, 5, 7]
    
    for symbol in config.WATCHLIST:
        safe_name = symbol.replace('/', '_')
        file_path = os.path.join(BASE_DIR, "data", "4h", f"{safe_name}_history.csv")
        
        if not os.path.exists(file_path): continue
            
        df = indicators.calculate_indicators(pd.read_csv(file_path))
        best_pnl, best_cfg = -9999.0, {"ADX_THRESHOLD": 15, "SWING_WINDOW": 3, "TP_RATIO": 1.5, "SL_RATIO": 1.0}
        
        for adx in adx_options:
            for sw in swing_options:
                pnl, trades = evaluate_parameters(symbol, df, adx, sw, 1.5, 1.0)
                if trades > 3 and pnl > best_pnl:
                    best_pnl, best_cfg = pnl, {"ADX_THRESHOLD": adx, "SWING_WINDOW": sw, "TP_RATIO": 1.5, "SL_RATIO": 1.0}
        
        best_params_dict[symbol] = best_cfg
        print(f"✅ {symbol} تنظیم شد: {best_cfg}")

    with open(params_file, "w") as f:
        json.dump(best_params_dict, f, indent=4)
    print("✨ فایل best_params.json با موفقیت آپدیت شد.")

if __name__ == "__main__":
    optimize_all()

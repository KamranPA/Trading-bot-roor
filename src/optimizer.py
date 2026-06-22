# ---------------------------------------------------------
# FILE PATH: src/optimizer.py (v9.7 - Timestamp + TP_RATIO Optimized)
# تغییرات نسبت به v9.6:
#   1. اضافه شدن timestamp به best_params.json (همیشه commit میشه)
#   2. ترتیب اجرا: بعد از train_model.py
# ---------------------------------------------------------
import os
import sys
import json
import datetime
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from src import indicators, strategy_utils
from src.brain import TradingBrain


def evaluate_parameters(symbol, df, adx_th, swing_w, tp_r, sl_r, brain=None):
    df_copy = df.copy()
    if 'feat_adx' not in df_copy.columns:
        df_copy = indicators.calculate_indicators(df_copy)

    if brain is None:
        brain = TradingBrain()

    ai_threshold = float(getattr(config, 'AI_THRESHOLD', 65.0))
    min_score    = float(getattr(config, 'MIN_REQUIRED_SCORE', 65))
    max_sl_pct   = float(getattr(config, 'MAX_SL_PERCENT', 0.05))
    w_ai  = float(getattr(config, 'WEIGHT_AI',  40))
    w_adx = float(getattr(config, 'WEIGHT_ADX', 20))
    w_rsi = float(getattr(config, 'WEIGHT_RSI', 20))
    w_ema = float(getattr(config, 'WEIGHT_EMA', 20))
    w_sum = (w_ai + w_adx + w_rsi + w_ema) or 100.0

    split_idx = int(len(df_copy) * 0.8)

    ai_total_trades = 0
    ai_total_pnl    = 0.0
    is_in_position  = False
    entry_price, direction, stop_loss, tp2 = 0.0, "", 0.0, 0.0

    for i in range(split_idx, len(df_copy)):
        current_candle = df_copy.iloc[i]
        high_price  = float(current_candle['High'])
        low_price   = float(current_candle['Low'])
        close_price = float(current_candle['Close'])

        if is_in_position:
            pnl = 0.0
            closed = False
            if direction == "LONG":
                if low_price <= stop_loss:
                    pnl = ((stop_loss - entry_price) / entry_price) * 100
                    closed = True
                elif high_price >= tp2:
                    pnl = ((tp2 - entry_price) / entry_price) * 100
                    closed = True
            elif direction == "SHORT":
                if high_price >= stop_loss:
                    pnl = ((entry_price - stop_loss) / entry_price) * 100
                    closed = True
                elif low_price <= tp2:
                    pnl = ((entry_price - tp2) / entry_price) * 100
                    closed = True

            if closed:
                ai_total_pnl    += pnl
                ai_total_trades += 1
                is_in_position   = False
            continue

        current_adx  = float(current_candle.get('feat_adx', 0))
        current_rsi  = float(current_candle.get('feat_rsi', 50))
        rsi_momentum = float(current_candle.get('feat_rsi_momentum', 0))
        dev_val      = abs(float(current_candle.get('feat_ema_deviation', 0)))
        atr_val      = float(current_candle.get('atr', current_candle.get('feat_atr_percent', 1.0)))

        if current_adx >= adx_th:
            adx_score = min(100.0, 50.0 + (current_adx - adx_th) * 2.5)
        else:
            adx_score = max(0.0, (current_adx / (adx_th + 1e-10)) * 50.0)

        if current_rsi > 50:
            rsi_score = min(100.0, max(0.0, 50.0 + rsi_momentum * 5))
        else:
            rsi_score = min(100.0, max(0.0, 50.0 + (-rsi_momentum) * 5))

        ema_score = min(100.0, (dev_val / 5.0) * 100.0)

        try:
            raw = brain.predict_probability(symbol, {
                'feat_adx':           current_adx,
                'feat_atr_percent':   float(current_candle.get('feat_atr_percent', 0)),
                'feat_rsi':           current_rsi,
                'feat_trend_line':    float(current_candle.get('feat_trend_line', 0)),
                'feat_ema_deviation': dev_val,
                'feat_rsi_momentum':  rsi_momentum,
                'feat_body_ratio':    float(current_candle.get('feat_body_ratio', 0)),
            })
            ai_score = float(raw) * 100.0 if float(raw) <= 1.0 else float(raw)
        except Exception:
            ai_score = 0.0

        ai_approved = ai_score >= ai_threshold
        total_score = (
            ai_score * w_ai + adx_score * w_adx + rsi_score * w_rsi + ema_score * w_ema
        ) / w_sum

        if total_score < min_score or not ai_approved:
            continue

        df_slice        = df_copy.iloc[:i + 1]
        last_swing_high = strategy_utils.find_last_swing(df_slice, 'high', swing_w)
        last_swing_low  = strategy_utils.find_last_swing(df_slice, 'low',  swing_w)

        if last_swing_high is None or last_swing_low is None:
            continue

        sl_dist = min(1.5 * atr_val * sl_r, close_price * max_sl_pct)
        if sl_dist <= 0:
            continue

        if high_price > last_swing_high and current_rsi > 50:
            is_in_position = True
            direction      = "LONG"
            entry_price    = close_price
            stop_loss      = entry_price - sl_dist
            tp2            = entry_price + sl_dist * tp_r
        elif low_price < last_swing_low and current_rsi < 50:
            is_in_position = True
            direction      = "SHORT"
            entry_price    = close_price
            stop_loss      = entry_price + sl_dist
            tp2            = entry_price - sl_dist * tp_r

    return ai_total_pnl, ai_total_trades


def optimize_all(mode="backtest"):
    print(f"⚙️ شروع بهینه‌سازی کامل پارامترها (mode={mode})...")
    params_file      = os.path.join(BASE_DIR, "best_params.json")
    best_params_dict = {}

    adx_options   = [15, 20, 25]
    swing_options = [3, 5, 7]
    tp_options    = [1.5, 2.0, 2.5]

    brain = TradingBrain()

    for symbol in config.WATCHLIST:
        safe_name = symbol.replace('/', '_')
        file_path = os.path.join(BASE_DIR, "data", "4h", f"{safe_name}_history.csv")

        if not os.path.exists(file_path):
            print(f"⚠️ فایل CSV برای {symbol} پیدا نشد — skip")
            continue

        df = indicators.calculate_indicators(pd.read_csv(file_path))

        best_pnl = -9999.0
        best_cfg = {
            "ADX_THRESHOLD": config.ADX_THRESHOLD,
            "SWING_WINDOW":  config.SWING_WINDOW,
            "TP_RATIO":      config.TP_RATIO,
            "SL_RATIO":      config.SL_RATIO,
        }

        for adx in adx_options:
            for sw in swing_options:
                for tp in tp_options:
                    pnl, trades = evaluate_parameters(
                        symbol, df, adx, sw, tp, 1.0, brain=brain
                    )
                    if trades > 3 and pnl > best_pnl:
                        best_pnl = pnl
                        best_cfg = {
                            "ADX_THRESHOLD": adx,
                            "SWING_WINDOW":  sw,
                            "TP_RATIO":      tp,
                            "SL_RATIO":      1.0,
                        }

        best_params_dict[symbol] = best_cfg
        print(f"✅ {symbol}: ADX={best_cfg['ADX_THRESHOLD']} SW={best_cfg['SWING_WINDOW']} TP={best_cfg['TP_RATIO']} | PnL={best_pnl:.2f}")

    best_params_dict['_updated_at'] = datetime.datetime.utcnow().isoformat()

    with open(params_file, "w") as f:
        json.dump(best_params_dict, f, indent=4)
    print("✨ فایل best_params.json با موفقیت آپدیت شد.")


if __name__ == "__main__":
    optimize_all()

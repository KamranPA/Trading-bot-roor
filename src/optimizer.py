# ---------------------------------------------------------
# FILE PATH: src/optimizer.py (v9.8 - Fixed Column Names + Workflow Integration)
# تغییرات نسبت به v9.7:
#   1. نرمال‌سازی نام ستون‌ها (High/Low/Close و high/low/close هر دو کار می‌کنند)
#   2. بررسی وجود فایل pkl قبل از اجرا
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
from src import strategy_utils
from src.indicators import TechnicalIndicators
from src.brain import TradingBrain


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    ستون‌ها را به حرف بزرگ استاندارد تبدیل می‌کند.
    fetcher.py: Timestamp, Open, High, Low, Close, Volume
    indicators: ممکن است به حرف کوچک تبدیل کند
    این تابع هر دو حالت را به حرف بزرگ برمی‌گرداند.
    """
    col_map = {}
    for col in df.columns:
        if col.lower() == 'open':
            col_map[col] = 'Open'
        elif col.lower() == 'high':
            col_map[col] = 'High'
        elif col.lower() == 'low':
            col_map[col] = 'Low'
        elif col.lower() == 'close':
            col_map[col] = 'Close'
        elif col.lower() == 'volume':
            col_map[col] = 'Volume'
        elif col.lower() == 'timestamp':
            col_map[col] = 'Timestamp'
    if col_map:
        df = df.rename(columns=col_map)
    return df


def evaluate_parameters(symbol, df, adx_th, swing_w, tp_r, sl_r, brain=None):
    df_copy = _normalize_columns(df.copy())

    # محاسبه اندیکاتورها اگه وجود نداشتن
    if 'ADX' not in df_copy.columns and 'feat_adx' not in df_copy.columns:
        df_copy, _ = TechnicalIndicators.calculate_all_features(df_copy, symbol=symbol)
        df_copy = _normalize_columns(df_copy)

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

        # خواندن قیمت‌ها — با پشتیبانی از هر دو حالت حرف بزرگ/کوچک
        high_price  = float(current_candle.get('High',  current_candle.get('high',  0)))
        low_price   = float(current_candle.get('Low',   current_candle.get('low',   0)))
        close_price = float(current_candle.get('Close', current_candle.get('close', 0)))

        if high_price == 0 or low_price == 0 or close_price == 0:
            continue

        if is_in_position:
            pnl    = 0.0
            closed = False
            if direction == "LONG":
                if low_price <= stop_loss:
                    pnl    = ((stop_loss - entry_price) / entry_price) * 100
                    closed = True
                elif high_price >= tp2:
                    pnl    = ((tp2 - entry_price) / entry_price) * 100
                    closed = True
            elif direction == "SHORT":
                if high_price >= stop_loss:
                    pnl    = ((entry_price - stop_loss) / entry_price) * 100
                    closed = True
                elif low_price <= tp2:
                    pnl    = ((entry_price - tp2) / entry_price) * 100
                    closed = True

            if closed:
                ai_total_pnl    += pnl
                ai_total_trades += 1
                is_in_position   = False
            continue

        # خواندن اندیکاتورها با پشتیبانی از نام‌های جدید و قدیمی
        current_adx  = float(current_candle.get('ADX',          current_candle.get('feat_adx',           0)))
        current_rsi  = float(current_candle.get('RSI',          current_candle.get('feat_rsi',           50)))
        rsi_momentum = float(current_candle.get('RSI_momentum', current_candle.get('feat_rsi_momentum',  0)))
        dev_val      = abs(float(current_candle.get('EMA_diff', current_candle.get('feat_ema_deviation', 0))))
        atr_val      = float(current_candle.get('ATR',          current_candle.get('feat_atr_percent',   1.0)))

        if atr_val == 0:
            atr_val = close_price * 0.01  # fallback: 1% از قیمت

        # محاسبه score ها
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
                'feat_atr_percent':   atr_val,
                'feat_rsi':           current_rsi,
                'feat_trend_line':    float(current_candle.get('Trend_line',  current_candle.get('feat_trend_line',  0))),
                'feat_ema_deviation': dev_val,
                'feat_rsi_momentum':  rsi_momentum,
                'feat_body_ratio':    float(current_candle.get('Body_ratio',  current_candle.get('feat_body_ratio',  0))),
            })
            if raw is None:
                # مدلی وجود ندارد — از میانگین استفاده می‌کنیم
                ai_score    = 50.0
                ai_approved = True
            else:
                ai_score    = float(raw) * 100.0 if float(raw) <= 1.0 else float(raw)
                ai_approved = ai_score >= ai_threshold
        except Exception:
            ai_score    = 50.0
            ai_approved = True

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
    print(f"شروع بهینه‌سازی کامل پارامترها (mode={mode})...")
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
            print(f"فایل CSV برای {symbol} پیدا نشد - skip")
            continue

        # لود CSV و نرمال‌سازی ستون‌ها
        df_raw = pd.read_csv(file_path)
        df_raw = _normalize_columns(df_raw)

        df, meta = TechnicalIndicators.calculate_all_features(df_raw, symbol=symbol)

        if not meta.get('success', False):
            print(f"محاسبه اندیکاتورها برای {symbol} ناموفق بود - skip")
            continue

        df = _normalize_columns(df)

        best_pnl = -9999.0
        best_cfg = {
            "ADX_THRESHOLD": config.ADX_THRESHOLD,
            "SWING_WINDOW":  config.SWING_WINDOW,
            "TP_RATIO":      config.TP_RATIO,
            "SL_RATIO":      config.SL_RATIO,
        }

        total_combos = len(adx_options) * len(swing_options) * len(tp_options)
        tested = 0

        for adx in adx_options:
            for sw in swing_options:
                for tp in tp_options:
                    tested += 1
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
        print(
            f"{symbol}: ADX={best_cfg['ADX_THRESHOLD']} "
            f"SW={best_cfg['SWING_WINDOW']} "
            f"TP={best_cfg['TP_RATIO']} | "
            f"PnL={best_pnl:.2f}% ({tested} ترکیب تست شد)"
        )

    best_params_dict['_updated_at'] = datetime.datetime.utcnow().isoformat()

    with open(params_file, "w") as f:
        json.dump(best_params_dict, f, indent=4)

    print("فایل best_params.json با موفقیت آپدیت شد.")
    return best_params_dict


if __name__ == "__main__":
    optimize_all()

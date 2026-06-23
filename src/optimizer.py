# FILE PATH: src/optimizer.py (v10.2 - fix High/Low case for strategy_utils)
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
    col_map = {}
    for col in df.columns:
        lower = col.lower()
        if lower in ('open', 'high', 'low', 'close', 'volume', 'timestamp'):
            col_map[col] = lower
    if col_map:
        df = df.rename(columns=col_map)
    df = df.loc[:, ~df.columns.duplicated(keep='first')]
    return df


def _add_uppercase_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """اضافه کردن ستون‌های با حرف بزرگ برای سازگاری با strategy_utils"""
    if 'high'  in df.columns: df['High']  = df['high']
    if 'low'   in df.columns: df['Low']   = df['low']
    if 'open'  in df.columns: df['Open']  = df['open']
    if 'close' in df.columns: df['Close'] = df['close']
    if 'feat_atr_percent' in df.columns and 'atr' not in df.columns:
        df['atr'] = (df['feat_atr_percent'] / 100.0) * df['close']
    return df


def evaluate_parameters(symbol, df, adx_th, swing_w, tp_r, sl_r, brain=None):
    df_copy = _normalize_columns(df.copy())
    df_copy = _add_uppercase_aliases(df_copy)

    if brain is None:
        brain = TradingBrain()

    min_score  = float(getattr(config, 'MIN_REQUIRED_SCORE', 65))
    max_sl_pct = float(getattr(config, 'MAX_SL_PERCENT', 0.05))
    w_ai  = float(getattr(config, 'WEIGHT_AI',  40))
    w_adx = float(getattr(config, 'WEIGHT_ADX', 20))
    w_rsi = float(getattr(config, 'WEIGHT_RSI', 20))
    w_ema = float(getattr(config, 'WEIGHT_EMA', 20))

    split_idx = int(len(df_copy) * 0.8)

    ai_total_trades = 0
    ai_total_pnl    = 0.0
    is_in_position  = False
    entry_price     = 0.0
    direction       = ""
    stop_loss       = 0.0
    tp2             = 0.0

    for i in range(split_idx, len(df_copy)):
        row = df_copy.iloc[i]

        high_price  = float(row.get('high',  0))
        low_price   = float(row.get('low',   0))
        close_price = float(row.get('close', 0))

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

        current_adx  = float(row.get('feat_adx',          row.get('adx', 0)))
        current_rsi  = float(row.get('feat_rsi',          row.get('rsi', 50)))
        rsi_momentum = float(row.get('feat_rsi_momentum', row.get('rsi_momentum', 0)))
        dev_val      = abs(float(row.get('feat_ema_deviation', row.get('ema_diff', 0))))
        atr_pct      = float(row.get('feat_atr_percent',  0))
        trend_line   = float(row.get('feat_trend_line',   row.get('trend_line', 0)))
        body_ratio   = float(row.get('feat_body_ratio',   row.get('body_ratio', 0)))
        volume_ratio = float(row.get('feat_volume_ratio', row.get('volume_ratio', 1.0)))

        atr_val = (atr_pct / 100.0) * close_price if atr_pct > 0 else close_price * 0.01

        adx_score = (
            min(100.0, 50.0 + (current_adx - adx_th) * 2.5)
            if current_adx >= adx_th
            else max(0.0, (current_adx / (adx_th + 1e-10)) * 50.0)
        )
        rsi_score = (
            min(100.0, max(0.0, 50.0 + rsi_momentum * 5))
            if current_rsi > 50
            else min(100.0, max(0.0, 50.0 + (-rsi_momentum) * 5))
        )
        ema_score = min(100.0, (dev_val / 5.0) * 100.0)

        try:
            raw = brain.predict_probability(symbol, {
                'feat_adx':           current_adx,
                'feat_atr_percent':   atr_pct,
                'feat_rsi':           current_rsi,
                'feat_trend_line':    trend_line,
                'feat_ema_deviation': dev_val,
                'feat_rsi_momentum':  rsi_momentum,
                'feat_body_ratio':    body_ratio,
                'feat_volume_ratio':  volume_ratio,
            })
            if raw is None:
                ai_score = 50.0
                w_ai_eff = 0.0
            else:
                ai_score = float(raw) * 100.0 if float(raw) <= 1.0 else float(raw)
                w_ai_eff = w_ai
        except Exception:
            ai_score = 50.0
            w_ai_eff = 0.0

        w_sum_eff   = (w_ai_eff + w_adx + w_rsi + w_ema) or 100.0
        total_score = (
            ai_score * w_ai_eff + adx_score * w_adx + rsi_score * w_rsi + ema_score * w_ema
        ) / w_sum_eff

        if total_score < min_score:
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
    print(f"شروع بهینه‌سازی (mode={mode})...")
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

        df_raw = pd.read_csv(file_path)
        df_raw = _normalize_columns(df_raw)

        df, meta = TechnicalIndicators.calculate_all_features(df_raw, symbol=symbol)
        if not meta.get('success', False):
            print(f"محاسبه اندیکاتورها برای {symbol} ناموفق - skip")
            continue

        df = _normalize_columns(df)
        df = _add_uppercase_aliases(df)

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
                    if pnl > best_pnl:
                        best_pnl = pnl
                        best_cfg = {
                            "ADX_THRESHOLD": adx,
                            "SWING_WINDOW":  sw,
                            "TP_RATIO":      tp,
                            "SL_RATIO":      1.0,
                        }

        best_params_dict[symbol] = best_cfg
        print(f"{symbol}: ADX={best_cfg['ADX_THRESHOLD']} SW={best_cfg['SWING_WINDOW']} "
              f"TP={best_cfg['TP_RATIO']} | PnL={best_pnl:.2f}%")

    best_params_dict['_updated_at'] = datetime.datetime.utcnow().isoformat()

    with open(params_file, "w") as f:
        json.dump(best_params_dict, f, indent=4)

    print("best_params.json آپدیت شد.")
    return best_params_dict


if __name__ == "__main__":
    optimize_all()

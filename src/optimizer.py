# FILE PATH: src/optimizer.py (v10.3 - Fully Aligned with strategy.py + backtester.py)
# تغییرات نسبت به v10.2:
#   ✅ فیلتر حجم per-candle اضافه شد (مثل strategy.py)
#   ✅ نام symbol برای brain نرمال‌سازی شد (BTCUSDT → BTC/USDT)
#   ✅ ATR مطلق — ابتدا از ستون 'atr'/'ATR' خوانده می‌شود، بعد از feat_atr_percent
#   ✅ ai_approved (AI_THRESHOLD) چک می‌شود
#   ✅ MAX_OPEN_POSITIONS پشتیبانی شد (مثل backtester)
#   ✅ feat_volume_ratio از features مدل حذف شد (در AI_FEATURES نیست)

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


# ─── توابع کمکی مشترک ────────────────────────────────────────────────────────

def _to_brain_symbol(symbol: str) -> str:
    """BTCUSDT → BTC/USDT برای brain.py — یکسان با backtester.py"""
    if '/' not in symbol and 'USDT' in symbol:
        base = symbol.replace('USDT', '')
        return f"{base}/USDT"
    return symbol


def _get_volume_threshold(symbol: str) -> float:
    """یکسان با strategy.py و backtester.py"""
    thresholds = getattr(config, 'VOLUME_THRESHOLDS', {})
    if symbol in thresholds:
        return float(thresholds[symbol])
    alt = symbol.replace('/', '')
    if alt in thresholds:
        return float(thresholds[alt])
    return 0.0


def _passes_volume_filter(row: pd.Series, symbol: str) -> bool:
    """یکسان با strategy.py و backtester.py"""
    if not getattr(config, 'ENABLE_VOLUME_FILTER', False):
        return True
    threshold = _get_volume_threshold(symbol)
    if threshold <= 0:
        return True
    vol = row.get('volume', row.get('Volume', 0))
    try:
        return float(vol) >= threshold
    except (TypeError, ValueError):
        return True


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
    """
    اضافه کردن ستون‌های Capitalized برای سازگاری با strategy_utils.find_last_swing
    که از df['High'] و df['Low'] استفاده می‌کند.
    یکسان با indicators.py _restore_capitalized_ohlcv()
    """
    for lower, upper in [('high','High'),('low','Low'),('open','Open'),
                          ('close','Close'),('volume','Volume')]:
        if lower in df.columns and upper not in df.columns:
            df[upper] = df[lower]
    # atr مطلق برای محاسبه SL
    if 'feat_atr_percent' in df.columns and 'atr' not in df.columns:
        df['atr'] = (df['feat_atr_percent'] / 100.0) * df['close']
    return df


def _get_atr(row: pd.Series, close_price: float) -> float:
    """
    خواندن ATR مطلق — یکسان با backtester.py و strategy.py:
    1. ابتدا از ستون 'atr' یا 'ATR' (مطلق > 1)
    2. اگر نبود، از feat_atr_percent (همیشه درصد است)
    3. فال‌بک: 1% قیمت
    """
    atr_raw = float(row.get('atr', row.get('ATR', 0)) or 0)
    if atr_raw > 1.0:
        return atr_raw
    atr_pct = float(row.get('feat_atr_percent', 0) or 0)
    if atr_pct > 0:
        return (atr_pct / 100.0) * close_price
    return close_price * 0.01


# ─── evaluate_parameters ─────────────────────────────────────────────────────

def evaluate_parameters(symbol, df, adx_th, swing_w, tp_r, sl_r, brain=None):
    """
    ارزیابی پارامترها روی ۲۰٪ آخر داده (validation set).
    رفتار کاملاً یکسان با backtester.py و strategy.py.
    """
    df_copy = _normalize_columns(df.copy())
    df_copy = _add_uppercase_aliases(df_copy)

    if brain is None:
        brain = TradingBrain()

    brain_symbol  = _to_brain_symbol(symbol)          # ✅ FIX: BTCUSDT → BTC/USDT
    min_score     = float(getattr(config, 'MIN_REQUIRED_SCORE', 65))
    ai_threshold  = float(getattr(config, 'AI_THRESHOLD',       65.0))
    max_sl_pct    = float(getattr(config, 'MAX_SL_PERCENT',      0.05))
    max_open      = int(getattr(config,   'MAX_OPEN_POSITIONS',  999))
    w_ai  = float(getattr(config, 'WEIGHT_AI',  40))
    w_adx = float(getattr(config, 'WEIGHT_ADX', 20))
    w_rsi = float(getattr(config, 'WEIGHT_RSI', 20))
    w_ema = float(getattr(config, 'WEIGHT_EMA', 20))

    split_idx   = int(len(df_copy) * 0.8)
    open_trades = []
    total_pnl   = 0.0
    total_trades = 0

    for i in range(split_idx, len(df_copy)):
        row         = df_copy.iloc[i]
        high_price  = float(row.get('high',  0))
        low_price   = float(row.get('low',   0))
        close_price = float(row.get('close', 0))

        if high_price == 0 or low_price == 0 or close_price == 0:
            continue

        # ── بستن معاملات باز ────────────────────────────────────────────────
        still_open = []
        for trade in open_trades:
            d   = trade['direction']
            sl  = trade['stop_loss']
            tp2 = trade['tp2']
            ep  = trade['entry_price']
            closed = False; pnl = 0.0

            if d == 'LONG':
                if low_price <= sl:
                    pnl = ((sl - ep) / ep) * 100; closed = True
                elif high_price >= tp2:
                    pnl = ((tp2 - ep) / ep) * 100; closed = True
            else:
                if high_price >= sl:
                    pnl = ((ep - sl) / ep) * 100; closed = True
                elif low_price <= tp2:
                    pnl = ((ep - tp2) / ep) * 100; closed = True

            if closed:
                total_pnl    += pnl
                total_trades += 1
            else:
                still_open.append(trade)
        open_trades = still_open

        # ── فیلتر حجم per-candle (✅ FIX: اضافه شد) ─────────────────────────
        if not _passes_volume_filter(row, symbol):
            continue

        # ── score ها ────────────────────────────────────────────────────────
        current_adx  = float(row.get('feat_adx',           row.get('ADX',  0)))
        current_rsi  = float(row.get('feat_rsi',           row.get('RSI',  50)))
        rsi_momentum = float(row.get('feat_rsi_momentum',  row.get('RSI_momentum', 0)))
        dev_val      = abs(float(row.get('feat_ema_deviation', row.get('EMA_diff', 0))))
        atr_pct      = float(row.get('feat_atr_percent',   0))
        trend_line   = float(row.get('feat_trend_line',    row.get('Trend_line', 0)))
        body_ratio   = float(row.get('feat_body_ratio',    row.get('Body_ratio', 0)))

        # ✅ FIX: ATR مطلق — یکسان با backtester.py
        atr_val = _get_atr(row, close_price)

        adx_score = (min(100.0, 50.0 + (current_adx - adx_th) * 2.5)
                     if current_adx >= adx_th
                     else max(0.0, (current_adx / (adx_th + 1e-10)) * 50.0))

        rsi_score = (min(100.0, max(0.0, 50.0 + rsi_momentum * 5))
                     if current_rsi > 50
                     else min(100.0, max(0.0, 50.0 + (-rsi_momentum) * 5)))

        ema_score = min(100.0, (dev_val / 5.0) * 100.0)

        # ── AI score ────────────────────────────────────────────────────────
        ai_score    = 0.0
        ai_approved = True
        w_ai_eff    = 0.0

        model_active = brain.has_model(brain_symbol)  # ✅ FIX: brain_symbol
        if model_active:
            try:
                raw = brain.predict_probability(brain_symbol, {  # ✅ FIX
                    'feat_adx':           current_adx,
                    'feat_atr_percent':   atr_pct,
                    'feat_rsi':           current_rsi,
                    'feat_trend_line':    trend_line,
                    'feat_ema_deviation': dev_val,
                    'feat_rsi_momentum':  rsi_momentum,
                    'feat_body_ratio':    body_ratio,
                    # ✅ FIX: feat_volume_ratio حذف شد (در AI_FEATURES نیست)
                })
                if raw is not None:
                    ai_score    = float(raw) * 100.0 if float(raw) <= 1.0 else float(raw)
                    ai_approved = ai_score >= ai_threshold  # ✅ FIX: اضافه شد
                    w_ai_eff    = w_ai
            except Exception:
                ai_approved = False

        w_sum_eff   = (w_ai_eff + w_adx + w_rsi + w_ema) or 100.0
        total_score = (
            ai_score * w_ai_eff +
            adx_score * w_adx +
            rsi_score * w_rsi +
            ema_score * w_ema
        ) / w_sum_eff

        # ✅ FIX: ai_approved هم چک می‌شود — یکسان با backtester
        if total_score < min_score or not ai_approved:
            continue

        # ✅ FIX: MAX_OPEN_POSITIONS چک می‌شود — یکسان با backtester
        if len(open_trades) >= max_open:
            continue

        df_slice        = df_copy.iloc[:i + 1]
        last_swing_high = strategy_utils.find_last_swing(df_slice, 'high', swing_w)
        last_swing_low  = strategy_utils.find_last_swing(df_slice, 'low',  swing_w)

        if last_swing_high is None or last_swing_low is None:
            continue

        sl_dist = min(1.5 * atr_val * sl_r, close_price * max_sl_pct)
        if sl_dist <= 0:
            continue

        trade_id = f"{symbol}_{i}"

        if high_price > last_swing_high and current_rsi > 50:
            open_trades.append({
                'id': trade_id, 'direction': 'LONG',
                'entry_price': close_price,
                'stop_loss':   close_price - sl_dist,
                'tp2':         close_price + sl_dist * tp_r,
            })
        elif low_price < last_swing_low and current_rsi < 50:
            open_trades.append({
                'id': trade_id, 'direction': 'SHORT',
                'entry_price': close_price,
                'stop_loss':   close_price + sl_dist,
                'tp2':         close_price - sl_dist * tp_r,
            })

    # ── بستن معاملات باقی‌مانده با قیمت آخر ────────────────────────────────
    last_price = float(df_copy.iloc[-1]['close'])
    for trade in open_trades:
        ep = trade['entry_price']
        d  = trade['direction']
        pnl = ((last_price - ep) / ep * 100
               if d == 'LONG'
               else (ep - last_price) / ep * 100)
        total_pnl    += pnl
        total_trades += 1

    return total_pnl, total_trades


# ─── optimize_all ─────────────────────────────────────────────────────────────

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

        try:
            df_raw = pd.read_csv(file_path)
        except Exception as e:
            print(f"❌ خطا در خواندن {symbol}: {e}")
            continue

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
        print(
            f"{symbol}: ADX={best_cfg['ADX_THRESHOLD']} "
            f"SW={best_cfg['SWING_WINDOW']} "
            f"TP={best_cfg['TP_RATIO']} | PnL={best_pnl:.2f}%"
        )

    best_params_dict['_updated_at'] = datetime.datetime.utcnow().isoformat()

    with open(params_file, "w") as f:
        json.dump(best_params_dict, f, indent=4)

    print("✅ best_params.json آپدیت شد.")
    return best_params_dict


if __name__ == "__main__":
    optimize_all()

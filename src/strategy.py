"""
FILE PATH: src/strategy.py (v10.0 - generate_signal + generate_signals)
اصلاح شده: اضافه شدن generate_signal() که main.py صدا می‌زند
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional

import config
from src.indicators import TechnicalIndicators
from src import strategy_utils

logger = logging.getLogger(__name__)


def generate_signal(
    df: pd.DataFrame,
    symbol: str,
    model=None,
    params: dict = None,
    open_positions_count: int = 0,
) -> dict:
    """
    تولید سیگنال برای یک ارز — صدا زده شده از main.py

    Returns:
        dict با کلیدهای:
          direction, entry_price, stop_loss, tp1, tp2,
          total_score, ai_score, adx_score, rsi_score, ema_score
        یا direction=None اگه سیگنالی نباشد
    """
    result = {
        'direction':    None,
        'entry_price':  None,
        'stop_loss':    None,
        'tp1':          None,
        'tp2':          None,
        'total_score':  0.0,
        'ai_score':     0.0,
        'adx_score':    0.0,
        'rsi_score':    0.0,
        'ema_score':    0.0,
    }

    if params is None:
        params = {}

    # پارامترها با fallback به config
    adx_th    = float(params.get('ADX_THRESHOLD', getattr(config, 'ADX_THRESHOLD', 15.0)))
    swing_w   = int(params.get('SWING_WINDOW',    getattr(config, 'SWING_WINDOW',   3)))
    sl_ratio  = float(params.get('SL_RATIO',      getattr(config, 'SL_RATIO',       1.0)))
    tp_ratio  = float(params.get('TP_RATIO',      getattr(config, 'TP_RATIO',       1.5)))
    min_score = float(getattr(config, 'MIN_REQUIRED_SCORE', 65))
    max_sl    = float(getattr(config, 'MAX_SL_PERCENT',     0.05))
    max_pos   = int(getattr(config,   'MAX_OPEN_POSITIONS', 5))

    w_ai  = float(getattr(config, 'WEIGHT_AI',  40))
    w_adx = float(getattr(config, 'WEIGHT_ADX', 20))
    w_rsi = float(getattr(config, 'WEIGHT_RSI', 20))
    w_ema = float(getattr(config, 'WEIGHT_EMA', 20))
    w_sum = (w_ai + w_adx + w_rsi + w_ema) or 100.0

    ai_threshold = float(getattr(config, 'AI_THRESHOLD', 65.0))

    # بررسی ظرفیت پوزیشن‌های باز
    if open_positions_count >= max_pos:
        logger.debug(f"{symbol}: پوزیشن‌های باز ({open_positions_count}) به حد مجاز رسیده")
        return result

    # آخرین کندل
    if df is None or df.empty:
        return result

    row = df.iloc[-1]

    # ── خواندن فیچرها — سازگار با feat_* و نام‌های معمول ──────────────────
    current_adx  = float(row.get('feat_adx',           row.get('ADX', 0)))
    current_rsi  = float(row.get('feat_rsi',           row.get('RSI', 50)))
    rsi_momentum = float(row.get('feat_rsi_momentum',  row.get('RSI_momentum', 0)))
    dev_val      = abs(float(row.get('feat_ema_deviation', row.get('EMA_diff', 0))))
    atr_pct      = float(row.get('feat_atr_percent',   0))
    trend_line   = float(row.get('feat_trend_line',    row.get('Trend_line', 0)))
    body_ratio   = float(row.get('feat_body_ratio',    row.get('Body_ratio', 0)))

    close_price = float(row.get('close', row.get('Close', 0)))
    high_price  = float(row.get('high',  row.get('High', 0)))
    low_price   = float(row.get('low',   row.get('Low', 0)))
    atr_val     = float(row.get('atr',   row.get('ATR', close_price * 0.01)))

    if close_price == 0:
        return result

    if atr_pct == 0 and atr_val > 0:
        atr_pct = (atr_val / close_price) * 100

    # ── score ها ────────────────────────────────────────────────────────────
    adx_score = min(100.0, 50.0 + (current_adx - adx_th) * 2.5) if current_adx >= adx_th \
                else max(0.0, (current_adx / (adx_th + 1e-10)) * 50.0)

    rsi_score = min(100.0, max(0.0, 50.0 + rsi_momentum * 5)) if current_rsi > 50 \
                else min(100.0, max(0.0, 50.0 + (-rsi_momentum) * 5))

    ema_score = min(100.0, (dev_val / 5.0) * 100.0)

    # ── AI score ────────────────────────────────────────────────────────────
    ai_score    = 50.0
    ai_approved = True
    w_ai_eff    = 0.0

    if model is not None and model.has_model(symbol):
        try:
            raw = model.predict_probability(symbol, {
                'feat_adx':           current_adx,
                'feat_atr_percent':   atr_pct,
                'feat_rsi':           current_rsi,
                'feat_trend_line':    trend_line,
                'feat_ema_deviation': dev_val,
                'feat_rsi_momentum':  rsi_momentum,
                'feat_body_ratio':    body_ratio,
            })
            if raw is not None:
                ai_score    = float(raw) * 100.0 if float(raw) <= 1.0 else float(raw)
                ai_approved = ai_score >= ai_threshold
                w_ai_eff    = w_ai
        except Exception as e:
            logger.warning(f"{symbol}: خطای AI score: {e}")

    w_sum_eff   = (w_ai_eff + w_adx + w_rsi + w_ema) or 100.0
    total_score = (ai_score * w_ai_eff + adx_score * w_adx + rsi_score * w_rsi + ema_score * w_ema) / w_sum_eff

    result['total_score'] = round(total_score, 2)
    result['ai_score']    = round(ai_score,    2)
    result['adx_score']   = round(adx_score,   2)
    result['rsi_score']   = round(rsi_score,   2)
    result['ema_score']   = round(ema_score,   2)

    if total_score < min_score or not ai_approved:
        logger.debug(f"{symbol}: score={total_score:.1f} ai_approved={ai_approved} — بدون سیگنال")
        return result

    # ── پیدا کردن swing ─────────────────────────────────────────────────────
    last_swing_high = strategy_utils.find_last_swing(df, 'high', swing_w)
    last_swing_low  = strategy_utils.find_last_swing(df, 'low',  swing_w)

    if last_swing_high is None or last_swing_low is None:
        logger.debug(f"{symbol}: swing یافت نشد")
        return result

    # ── تعیین جهت ───────────────────────────────────────────────────────────
    direction = None
    if high_price > last_swing_high and current_rsi > 50:
        direction = "LONG"
    elif low_price < last_swing_low and current_rsi < 50:
        direction = "SHORT"

    if direction is None:
        return result

    # ── محاسبه SL و TP ──────────────────────────────────────────────────────
    sl_dist = min(1.5 * atr_val * sl_ratio, close_price * max_sl)
    if sl_dist <= 0:
        return result

    if direction == "LONG":
        stop_loss = close_price - sl_dist
        tp1       = close_price + sl_dist
        tp2       = close_price + sl_dist * tp_ratio
    else:
        stop_loss = close_price + sl_dist
        tp1       = close_price - sl_dist
        tp2       = close_price - sl_dist * tp_ratio

    result.update({
        'direction':   direction,
        'entry_price': round(close_price, 6),
        'stop_loss':   round(stop_loss,   6),
        'tp1':         round(tp1,         6),
        'tp2':         round(tp2,         6),
    })

    logger.info(f"✅ سیگنال {symbol}: {direction} | score={total_score:.1f} | entry={close_price}")
    return result


def generate_signals(
    data_dict: Dict[str, pd.DataFrame],
    model=None,
    params_dict: dict = None,
    open_positions_count: int = 0,
) -> Dict[str, dict]:
    """
    تولید سیگنال برای چندین ارز — wrapper دسته‌ای
    """
    results = {}
    for symbol, df in data_dict.items():
        p = (params_dict or {}).get(symbol, {})
        results[symbol] = generate_signal(df, symbol, model=model, params=p,
                                          open_positions_count=open_positions_count)
    return results

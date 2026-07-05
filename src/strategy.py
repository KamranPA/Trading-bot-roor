"""
FILE PATH: src/strategy.py (v10.3 - Unified AI_THRESHOLD with backtester/optimizer)
تغییرات نسبت به v10.2:
  ✅ FIX: ai_threshold دیگر همیشه از config.AI_THRESHOLD ثابت خوانده نمی‌شود؛
     از src.ai_threshold.get_ai_threshold() استفاده می‌شود — دقیقاً همان
     منبعی که backtester.py و optimizer.py از قبل استفاده می‌کردند.
     این باعث می‌شود سیگنال زنده و بک‌تست/بهینه‌سازی از یک آستانه‌ی
     per-symbol کالیبره‌شده (خروجی train_model.py) استفاده کنند.
  ✅ نکته: فرمول TP1 (خط پایین) به‌عنوان مرجع نگه‌داشته شد (RR=1:1)؛
     backtester.py برای هماهنگی با همین‌جا اصلاح شد.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional

import config
from src.indicators import TechnicalIndicators
from src import strategy_utils
from src.volume_filter import passes_volume_filter, VOLUME_MULTIPLIER
from src.ai_threshold import get_ai_threshold

logger = logging.getLogger(__name__)

# ✅ FIX: دروازه‌ی سخت‌گیر AI (ai_approved) جدا از وزن AI در امتیاز کلی است.
# اگر مدل فعلی سیگنال قابل‌اعتمادی ندارد (AUC نزدیک 0.5 — تشخیص داده‌شده در
# جلسه‌ی دیباگ train_model.py)، این را در config.py برابر False بگذار تا
# دروازه‌ی AI دیگر سیگنال را رد نکند (زیرساخت مدل/آموزش دست‌نخورده می‌ماند
# تا اگر بعداً فیچرهای بهتری اضافه شد، دوباره True کنی).
AI_GATE_ENABLED = bool(getattr(config, 'AI_GATE_ENABLED', True))


# فیلتر حجم پویا — از ماژول مشترک src/volume_filter.py
# volume >= Volume_SMA_20 * VOLUME_MULTIPLIER (0.5)
_passes_volume_filter = passes_volume_filter


def generate_signal(
    df: pd.DataFrame,
    symbol: str,
    model=None,
    params: dict = None,
    open_positions_count: int = 0,
) -> dict:
    """
    تولید سیگنال برای یک ارز.

    ⚠️ مهم: score همیشه محاسبه می‌شود — حتی اگر سیگنالی صادر نشود.
    این باعث می‌شود scan_log همیشه مقادیر واقعی داشته باشد.

    Returns:
        dict با direction=None اگر سیگنالی نباشد،
        اما total_score/ai_score/... همیشه پر هستند.
    """
    # مقادیر پیش‌فرض
    result = {
        'direction':   None,
        'entry_price': None,
        'stop_loss':   None,
        'tp1':         None,
        'tp2':         None,
        'total_score': 0.0,
        'ai_score':    0.0,
        'adx_score':   0.0,
        'rsi_score':   0.0,
        'ema_score':   0.0,
        'pair':        symbol,
        'feat_adx':    0.0,
    }

    if params is None:
        params = {}

    # پارامترها
    adx_th    = float(params.get('ADX_THRESHOLD', getattr(config, 'ADX_THRESHOLD', 15.0)))
    swing_w   = int(params.get('SWING_WINDOW',    getattr(config, 'SWING_WINDOW',   3)))
    sl_ratio  = float(params.get('SL_RATIO',      getattr(config, 'SL_RATIO',       1.0)))
    tp_ratio  = float(params.get('TP_RATIO',      getattr(config, 'TP_RATIO',       1.5)))
    min_score = float(getattr(config, 'MIN_REQUIRED_SCORE', 65))
    max_sl    = float(getattr(config, 'MAX_SL_PERCENT',     0.05))
    max_pos   = int(getattr(config,   'MAX_OPEN_POSITIONS', 5))
    w_ai      = float(getattr(config, 'WEIGHT_AI',  40))
    w_adx     = float(getattr(config, 'WEIGHT_ADX', 20))
    w_rsi     = float(getattr(config, 'WEIGHT_RSI', 20))
    w_ema     = float(getattr(config, 'WEIGHT_EMA', 20))

    # ✅ FIX: آستانه‌ی AI per-symbol — یکسان با backtester.py/optimizer.py
    # اولویت: params (اگر صراحتاً پاس داده شده) > ai_thresholds.json کالیبره‌شده > config ثابت
    _default_ai_th = float(getattr(config, 'AI_THRESHOLD', 65.0))
    if 'AI_THRESHOLD' in params:
        ai_threshold = float(params['AI_THRESHOLD'])
    else:
        ai_threshold = get_ai_threshold(symbol, default=_default_ai_th)

    # ── بررسی اولیه df ───────────────────────────────────────────────────────
    if df is None or df.empty:
        return result

    row = df.iloc[-1]

    # خواندن قیمت‌ها
    close_price = float(row.get('close', row.get('Close', 0)))
    high_price  = float(row.get('high',  row.get('High',  0)))
    low_price   = float(row.get('low',   row.get('Low',   0)))
    atr_val     = float(row.get('atr',   row.get('ATR',   close_price * 0.01)))
    if atr_val < 1.0 and close_price > 0:
        atr_val = atr_val * close_price

    if close_price == 0:
        return result

    atr_pct = float(row.get('feat_atr_percent', 0))
    if atr_pct == 0 and atr_val > 0:
        atr_pct = (atr_val / close_price) * 100

    # ── خواندن فیچرها ────────────────────────────────────────────────────────
    current_adx  = float(row.get('feat_adx',           row.get('ADX', 0)))
    current_rsi  = float(row.get('feat_rsi',           row.get('RSI', 50)))
    rsi_momentum = float(row.get('feat_rsi_momentum',  row.get('RSI_momentum', 0)))
    dev_val      = abs(float(row.get('feat_ema_deviation', row.get('EMA_diff', 0))))
    trend_line   = float(row.get('feat_trend_line',    row.get('Trend_line', 0)))
    body_ratio   = float(row.get('feat_body_ratio',    row.get('Body_ratio', 0)))

    # ── ۱. محاسبه score (همیشه — قبل از هر فیلتری) ──────────────────────────
    adx_score = (min(100.0, 50.0 + (current_adx - adx_th) * 2.5)
                 if current_adx >= adx_th
                 else max(0.0, (current_adx / (adx_th + 1e-10)) * 50.0))

    rsi_score = (min(100.0, max(0.0, 50.0 + rsi_momentum * 5))
                 if current_rsi > 50
                 else min(100.0, max(0.0, 50.0 + (-rsi_momentum) * 5)))

    ema_score = min(100.0, (dev_val / 5.0) * 100.0)

    # ── ۲. AI score ──────────────────────────────────────────────────────────
    ai_score    = 50.0
    ai_approved = True
    w_ai_eff    = 0.0

    brain_symbol = symbol
    if '/' not in symbol and 'USDT' in symbol:
        brain_symbol = symbol.replace('USDT', '') + '/USDT'

    if model is not None and model.has_model(brain_symbol):
        try:
            raw = model.predict_probability(brain_symbol, {
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
    total_score = (
        ai_score  * w_ai_eff +
        adx_score * w_adx +
        rsi_score * w_rsi +
        ema_score * w_ema
    ) / w_sum_eff

    # ── score را همیشه در result ذخیره می‌کنیم ──────────────────────────────
    result['feat_adx']    = round(current_adx,  2)
    result['total_score'] = round(total_score,  2)
    result['ai_score']    = round(ai_score,     2)
    result['adx_score']   = round(adx_score,    2)
    result['rsi_score']   = round(rsi_score,    2)
    result['ema_score']   = round(ema_score,    2)

    # ── ۳. فیلترها (بعد از محاسبه score) ────────────────────────────────────

    # فیلتر حجم
    if not _passes_volume_filter(row, symbol):
        logger.debug(f"{symbol}: حجم کافی نیست | score={total_score:.1f}")
        return result  # score پر است، direction=None

    # ظرفیت پوزیشن
    if open_positions_count >= max_pos:
        logger.debug(f"{symbol}: پوزیشن‌های باز ({open_positions_count}) به حد رسیده | score={total_score:.1f}")
        return result

    # حداقل score
    if total_score < min_score or (AI_GATE_ENABLED and not ai_approved):
        logger.debug(f"{symbol}: score={total_score:.1f} ai_approved={ai_approved} "
                     f"(gate_enabled={AI_GATE_ENABLED}) — بدون سیگنال")
        return result

    # ── ۴. پیدا کردن swing ───────────────────────────────────────────────────
    last_swing_high = strategy_utils.find_last_swing(df, 'high', swing_w)
    last_swing_low  = strategy_utils.find_last_swing(df, 'low',  swing_w)

    if last_swing_high is None or last_swing_low is None:
        logger.debug(f"{symbol}: swing یافت نشد | score={total_score:.1f}")
        return result

    # ── ۵. تعیین جهت ─────────────────────────────────────────────────────────
    direction = None
    if high_price > last_swing_high and current_rsi > 50:
        direction = "LONG"
    elif low_price < last_swing_low and current_rsi < 50:
        direction = "SHORT"

    if direction is None:
        return result

    # ── ۶. محاسبه SL و TP ────────────────────────────────────────────────────
    # TP1 = فاصله‌ی برابر با SL (RR=1:1) — تارگت محافظه‌کارانه برای بستن جزئی.
    # TP2 = فاصله‌ی کامل با نسبت tp_ratio.
    # backtester.py برای هماهنگی دقیق با همین فرمول اصلاح شده است.
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

    logger.info(
        f"✅ سیگنال {symbol}: {direction} | "
        f"score={total_score:.1f} | AI_TH={ai_threshold:.1f} | entry={close_price:.4f}"
    )
    return result


def generate_signals(
    data_dict: Dict[str, pd.DataFrame],
    model=None,
    params_dict: dict = None,
    open_positions_count: int = 0,
) -> Dict[str, dict]:
    """تولید سیگنال برای چندین ارز — wrapper دسته‌ای"""
    results = {}
    for symbol, df in data_dict.items():
        p = (params_dict or {}).get(symbol, {})
        results[symbol] = generate_signal(
            df, symbol,
            model=model,
            params=p,
            open_positions_count=open_positions_count,
        )
    return results

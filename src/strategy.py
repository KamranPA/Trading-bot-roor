# ---------------------------------------------------------
# FILE PATH: src/strategy.py (v3.1 - Volume Filter Added)
# ---------------------------------------------------------
import logging
import datetime

import config
from src import database, strategy_utils

logger = logging.getLogger(__name__)


def is_blocked_by_8h_filter(pair: str, current_direction: str) -> bool:
    try:
        last_signal = database.get_last_signal_for_pair(pair)
        if not last_signal:
            return False
        last_direction = last_signal.get('direction')
        last_time      = last_signal.get('timestamp')
        if last_direction != current_direction or last_time is None:
            return False
        now = datetime.datetime.now(datetime.timezone.utc)
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=datetime.timezone.utc)
        return (now - last_time).total_seconds() / 3600 < 8
    except Exception as e:
        logger.warning("خطا در فیلتر ۸ ساعته برای %s: %s", pair, e)
        return False


def generate_signal(df, pair: str, model=None, params: dict = None,
                    open_positions_count: int = 0) -> dict:
    default_scores = {
        'total_score': 0.0, 'ai_score': 0.0,
        'rsi_score': 0.0, 'adx_score': 0.0, 'ema_score': 0.0,
        'direction': None,
    }

    if df is None or len(df) < 200:
        return default_scores

    if params is None:
        params = {}

    adx_thresh     = float(params.get('ADX_THRESHOLD', config.ADX_THRESHOLD))
    tp_ratio       = float(params.get('TP_RATIO',       config.TP_RATIO))
    sl_ratio       = float(params.get('SL_RATIO',       config.SL_RATIO))
    ai_threshold   = float(params.get('AI_THRESHOLD',   getattr(config, 'AI_THRESHOLD', 65.0)))
    swing_window   = int(params.get('SWING_WINDOW',     config.SWING_WINDOW))
    MAX_SL_PERCENT = float(getattr(config, 'MAX_SL_PERCENT', 0.05))

    candle = df.iloc[-1]

    w_ai  = float(getattr(config, 'WEIGHT_AI',  40))
    w_adx = float(getattr(config, 'WEIGHT_ADX', 20))
    w_rsi = float(getattr(config, 'WEIGHT_RSI', 20))
    w_ema = float(getattr(config, 'WEIGHT_EMA', 20))
    w_sum = (w_ai + w_adx + w_rsi + w_ema) or 100.0

    current_adx    = float(candle.get('feat_adx', 0))
    current_rsi    = float(candle.get('feat_rsi', 50))
    rsi_momentum   = float(candle.get('feat_rsi_momentum', 0))
    dev_val        = abs(float(candle.get('feat_ema_deviation', 0)))
    volume_ratio   = float(candle.get('feat_volume_ratio', 1.0))

    # فیلتر حجم — اگر حجم کمتر از ۸۰٪ میانگین باشه سیگنال صادر نمیشه
    if volume_ratio < 0.8:
        logger.debug("%s: حجم ناکافی (volume_ratio=%.2f) — رد شد", pair, volume_ratio)
        return default_scores

    adx_score = (
        min(100.0, 50.0 + (current_adx - adx_thresh) * 2.5)
        if current_adx >= adx_thresh
        else max(0.0, (current_adx / (adx_thresh + 1e-10)) * 50.0)
    )
    rsi_score = max(0.0, min(100.0,
        50.0 + rsi_momentum * 5 if current_rsi > 50 else 50.0 - rsi_momentum * 5
    ))
    ema_score = min(100.0, (dev_val / 5.0) * 100.0)

    features_dict = {
        'feat_adx':           current_adx,
        'feat_atr_percent':   float(candle.get('feat_atr_percent', 0)),
        'feat_rsi':           current_rsi,
        'feat_trend_line':    float(candle.get('feat_trend_line', 0)),
        'feat_ema_deviation': dev_val,
        'feat_rsi_momentum':  rsi_momentum,
        'feat_body_ratio':    float(candle.get('feat_body_ratio', 0)),
        'feat_volume_ratio':  volume_ratio,
    }

    model_active = (
        model is not None
        and hasattr(model, 'has_model')
        and model.has_model(pair)
    )

    ai_score    = 0.0
    ai_approved = True

    if model_active:
        try:
            raw = model.predict_probability(pair, features_dict)
            if raw is None:
                ai_approved = False
            else:
                ai_score    = float(raw) * 100.0 if float(raw) <= 1.0 else float(raw)
                ai_approved = ai_score >= ai_threshold
        except Exception as e:
            logger.error("خطا در پیش‌بینی AI برای %s: %s", pair, e)
            ai_approved = False

    if model_active:
        total_score = (
            ai_score * w_ai + adx_score * w_adx + rsi_score * w_rsi + ema_score * w_ema
        ) / w_sum
    else:
        w_ind = (w_adx + w_rsi + w_ema) or 60.0
        total_score = (
            adx_score * w_adx + rsi_score * w_rsi + ema_score * w_ema
        ) / w_ind

    score_data = {
        'total_score': round(total_score, 2),
        'ai_score':    round(ai_score,    2),
        'rsi_score':   round(rsi_score,   2),
        'adx_score':   round(adx_score,   2),
        'ema_score':   round(ema_score,   2),
        'direction':   None,
    }

    min_score     = float(getattr(config, 'MIN_REQUIRED_SCORE', 65))
    max_positions = getattr(config, 'MAX_OPEN_POSITIONS', 3)

    if total_score < min_score:
        return score_data
    if open_positions_count >= max_positions:
        return score_data
    if not ai_approved:
        return score_data

    last_swing_high = strategy_utils.find_last_swing(df, 'high', swing_window)
    last_swing_low  = strategy_utils.find_last_swing(df, 'low',  swing_window)
    if last_swing_high is None or last_swing_low is None:
        return score_data

    high_price  = float(candle['High'])
    low_price   = float(candle['Low'])
    close_price = float(candle['Close'])
    atr_val     = float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))

    risk_amount = (
        float(getattr(config, 'TOTAL_CAPITAL', 1000.0))
        * float(getattr(config, 'RISK_PERCENT', 1.0)) / 100.0
    )

    def _position_size(sl_dist: float) -> float:
        return round(risk_amount * close_price / sl_dist, 2) if sl_dist > 0 else 0.0

    if (high_price > last_swing_high
            and current_rsi > 50
            and not is_blocked_by_8h_filter(pair, "LONG")):

        sl_dist = min(1.5 * atr_val * sl_ratio, close_price * MAX_SL_PERCENT)
        if sl_dist <= 0:
            return score_data

        score_data.update({
            'pair':          pair,
            'direction':     'LONG',
            'entry_price':   round(close_price, 6),
            'stop_loss':     round(close_price - sl_dist, 6),
            'tp1':           round(close_price + sl_dist * tp_ratio / 2, 6),
            'tp2':           round(close_price + sl_dist * tp_ratio,     6),
            'swing_ref':     round(last_swing_high, 6),
            'position_size': _position_size(sl_dist),
            **features_dict,
        })
        logger.info("🟢 LONG %s | امتیاز: %.1f | Volume: %.2f | Entry: %.4f",
                    pair, total_score, volume_ratio, close_price)

    elif (low_price < last_swing_low
            and current_rsi < 50
            and not is_blocked_by_8h_filter(pair, "SHORT")):

        sl_dist = min(1.5 * atr_val * sl_ratio, close_price * MAX_SL_PERCENT)
        if sl_dist <= 0:
            return score_data

        score_data.update({
            'pair':          pair,
            'direction':     'SHORT',
            'entry_price':   round(close_price, 6),
            'stop_loss':     round(close_price + sl_dist, 6),
            'tp1':           round(close_price - sl_dist * tp_ratio / 2, 6),
            'tp2':           round(close_price - sl_dist * tp_ratio,     6),
            'swing_ref':     round(last_swing_low, 6),
            'position_size': _position_size(sl_dist),
            **features_dict,
        })
        logger.info("🔴 SHORT %s | امتیاز: %.1f | Volume: %.2f | Entry: %.4f",
                    pair, total_score, volume_ratio, close_price)

    return score_data

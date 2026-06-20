# ---------------------------------------------------------
# FILE PATH: src/strategy.py (UPDATED & SYNCED WITH DYNAMIC PARAMS)
# ---------------------------------------------------------
import config
from src import database, strategy_utils

def is_blocked_by_8h_filter(pair, current_direction):
    """بررسی فیلتر ۸ ساعته از دیتابیس"""
    try:
        # استفاده از دیتابیس ابری (تطابق با ساختار main.py)
        last_signal = database.get_last_signal_for_pair(pair)
        if last_signal:
            last_direction = last_signal.get('direction')
            last_time = last_signal.get('timestamp') # انتظار می‌رود به صورت datetime باشد
            
            import datetime
            now = datetime.datetime.utcnow()
            if last_direction == current_direction and (now - last_time).total_seconds() / 3600 < 8:
                return True
    except Exception as e:
        print(f"⚠️ خطا در بررسی فیلتر ۸ ساعته برای {pair}: {e}")
    return False

def generate_signal(df, pair, model=None, params=None):
    """
    نسخه جدید: استفاده از params جهت همگام‌سازی کامل با بکتست
    """
    default_scores = {
        'total_score': 0.0, 'ai_score': 0.0, 'rsi_score': 0.0, 'adx_score': 0.0, 'ema_score': 0.0,
        'direction': None
    }

    if df is None or len(df) < 200 or params is None:
        return default_scores

    # استخراج پارامترهای اختصاصی ارز از دیکشنری تزریق شده
    adx_thresh = float(params.get('ADX_THRESHOLD', config.ADX_THRESHOLD))
    tp_ratio = float(params.get('TP_RATIO', 1.5))
    sl_ratio = float(params.get('SL_RATIO', 1.0))
    risk_multiplier = float(params.get('RISK_MULTIPLIER', 1.0))
    ai_threshold = float(params.get('AI_THRESHOLD', 65.0))
    MAX_SL_PERCENT = getattr(config, 'MAX_SL_PERCENT', 0.03)

    idx = len(df) - 1
    candle = df.iloc[idx]
    
    # --- سیستم امتیازدهی هوشمند ---
    current_adx = float(candle.get('feat_adx', 0))
    adx_score = min(100.0, 50.0 + ((current_adx - adx_thresh) * 2.5)) if current_adx >= adx_thresh else max(0.0, (current_adx / (adx_thresh + 1e-10)) * 50.0)

    current_rsi = float(candle.get('feat_rsi', 50))
    rsi_momentum = float(candle.get('feat_rsi_momentum', 0))
    rsi_score = min(100.0, 50.0 + (rsi_momentum * 5) if (current_rsi > 50 and rsi_momentum > 0) else 50.0) if current_rsi > 50 else min(100.0, 50.0 + (-rsi_momentum * 5))

    dev_val = abs(float(candle.get('feat_ema_deviation', 0)))
    ema_score = min(100.0, (dev_val / 5.0) * 100.0)

    ai_score = 0.0
    features_dict = {
        'feat_adx': current_adx, 'feat_atr_percent': float(candle.get('feat_atr_percent', 0)),
        'feat_rsi': current_rsi, 'feat_trend_line': float(candle.get('feat_trend_line', 0)),
        'feat_ema_deviation': dev_val, 'feat_rsi_momentum': rsi_momentum, 'feat_body_ratio': float(candle.get('feat_body_ratio', 0))
    }

    ai_approved = False
    if model is not None:
        try:
            ai_score = model.predict_probability(pair, features_dict)
            ai_score = ai_score * 100.0 if ai_score <= 1.0 else ai_score
            ai_approved = ai_score >= ai_threshold
        except:
            return default_scores

    total_score = (ai_score * 0.40) + (adx_score * 0.20) + (rsi_score * 0.20) + (ema_score * 0.20)
    score_data = {'total_score': round(total_score, 2), 'ai_score': round(ai_score, 2), 'rsi_score': round(rsi_score, 2), 'adx_score': round(adx_score, 2), 'ema_score': round(ema_score, 2), 'direction': None}

    if total_score < 60.0 or database.get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
        return score_data

    # --- منطق ورود ---
    last_swing_high = strategy_utils.find_last_swing(df, 'high', int(params.get('SWING_WINDOW', config.SWING_WINDOW)))
    last_swing_low = strategy_utils.find_last_swing(df, 'low', int(params.get('SWING_WINDOW', config.SWING_WINDOW)))

    if last_swing_high is None or last_swing_low is None:
        return score_data

    high_price, low_price = float(candle['High']), float(candle['Low'])
    atr_val = float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))

    # ورود LONG/SHORT با ضرایب داینامیک
    if high_price > last_swing_high and current_rsi > 50 and ai_approved and not is_blocked_by_8h_filter(pair, "LONG"):
        sl_dist = min(1.5 * atr_val * sl_ratio, last_swing_high * MAX_SL_PERCENT)
        score_data.update({'pair': pair, 'direction': 'LONG', 'entry_price': round(last_swing_high, 4), 'stop_loss': round(last_swing_high - sl_dist, 4), 'tp1': round(last_swing_high + (sl_dist * tp_ratio / 2), 4), 'tp2': round(last_swing_high + (sl_dist * tp_ratio), 4), **features_dict})
    
    elif low_price < last_swing_low and current_rsi < 50 and ai_approved and not is_blocked_by_8h_filter(pair, "SHORT"):
        sl_dist = min(1.5 * atr_val * sl_ratio, last_swing_low * MAX_SL_PERCENT)
        score_data.update({'pair': pair, 'direction': 'SHORT', 'entry_price': round(last_swing_low, 4), 'stop_loss': round(last_swing_low + sl_dist, 4), 'tp1': round(last_swing_low - (sl_dist * tp_ratio / 2), 4), 'tp2': round(last_swing_low - (sl_dist * tp_ratio), 4), **features_dict})

    return score_data

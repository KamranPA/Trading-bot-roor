import os
import json
import sqlite3
import datetime
import config
from src import database, strategy_utils
import pandas as pd

def is_blocked_by_8h_filter(pair, current_direction):
    try:
        if not os.path.exists(database.DB_PATH):
            return False
        with sqlite3.connect(database.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT direction, timestamp FROM signals WHERE symbol = ? ORDER BY id DESC LIMIT 1",
                (pair,)
            )
            last_signal = cursor.fetchone()
            if last_signal:
                last_direction, last_time_str = last_signal
                if last_direction == current_direction:
                    clean_time_str = last_time_str.split('.')[0]
                    last_time = datetime.datetime.strptime(clean_time_str, '%Y-%m-%d %H:%M:%S')
                    now = datetime.datetime.utcnow()
                    if (now - last_time).total_seconds() / 3600 < 8:
                        return True
    except Exception as e:
        print(f"⚠️ خطا در بررسی فیلتر ۸ ساعته برای {pair}: {e}")
    return False

def generate_signal(df, pair, model=None):
    if df is None or len(df) < 200:
        return None

    candle = df.iloc[-1]
    if database.get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
        return None

    adx_thresh = config.ADX_THRESHOLD
    tp_ratio = 1.5
    sl_ratio = 1.0
    risk_multiplier = 1.0
    
    try:
        params_file = os.path.join(config.BASE_DIR, "best_params.json")
        if os.path.exists(params_file):
            with open(params_file, 'r') as f:
                all_params = json.load(f)
                pair_params = all_params.get(pair, all_params.get("DEFAULT", {}))
                adx_thresh = pair_params.get('adx_threshold', adx_thresh)
                tp_ratio = pair_params.get('tp_ratio', tp_ratio)
                sl_ratio = pair_params.get('sl_ratio', sl_ratio)
                risk_multiplier = pair_params.get('risk_multiplier', risk_multiplier)
    except Exception:
        pass

    if float(candle.get('feat_adx', 0)) < adx_thresh:
        return None

    last_swing_high = strategy_utils.find_last_swing(df, 'high', config.SWING_WINDOW)
    last_swing_low = strategy_utils.find_last_swing(df, 'low', config.SWING_WINDOW)

    if last_swing_high is None or last_swing_low is None:
        return None

    features_dict = {
        'feat_adx': float(candle.get('feat_adx', 0)),
        'feat_atr_percent': float(candle.get('feat_atr_percent', 0)),
        'feat_rsi': float(candle.get('feat_rsi', 0)),
        'feat_trend_line': float(candle.get('feat_trend_line', 0)),
        'feat_ema_deviation': float(candle.get('feat_ema_deviation', 0)),
        'feat_rsi_momentum': float(candle.get('feat_rsi_momentum', 0)),
        'feat_body_ratio': float(candle.get('feat_body_ratio', 0))
    }

    if model is not None:
        try:
            if not model.predict(pair, features_dict):
                return None
        except Exception as e:
            print(f"خطا در مدل هوش مصنوعی {pair}: {e}")

    def calculate_signal_score(direction):
        score = 50 
        if features_dict['feat_adx'] >= adx_thresh + 10: score += 20
        elif features_dict['feat_adx'] >= adx_thresh + 5: score += 10
        if model is not None: score += 10
        if direction == 'LONG':
            if 65 > features_dict['feat_rsi'] > 40: score += 10
            if features_dict['feat_ema_deviation'] > 0: score += 10
        elif direction == 'SHORT':
            if 60 > features_dict['feat_rsi'] > 35: score += 10
            if features_dict['feat_ema_deviation'] < 0: score += 10
        return min(score, 100)

    is_bullish_momentum = float(candle.get('feat_rsi', 50)) > 50
    is_bearish_momentum = float(candle.get('feat_rsi', 50)) < 50
    
    # لاجیک ورود
    result = None
    if float(candle['High']) > last_swing_high and is_bullish_momentum and not is_blocked_by_8h_filter(pair, "LONG"):
        entry_price = last_swing_high
        risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0) * risk_multiplier
        atr_val = float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))
        sl_dist = 1.5 * atr_val * sl_ratio
        tp_dist = sl_dist * tp_ratio
        
        result = {
            'pair': pair, 'direction': 'LONG', 'entry_price': round(entry_price, 4),
            'stop_loss': round(entry_price - sl_dist, 4), 'tp1': round(entry_price + (tp_dist / 2), 4),
            'tp2': round(entry_price + tp_dist, 4), 'position_size': round(min(risk_usd / ((sl_dist/entry_price)*100/100), config.TOTAL_CAPITAL), 2),
            'signal_score': calculate_signal_score('LONG'), **features_dict
        }

    elif float(candle['Low']) < last_swing_low and is_bearish_momentum and not is_blocked_by_8h_filter(pair, "SHORT"):
        entry_price = last_swing_low
        risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0) * risk_multiplier
        atr_val = float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))
        sl_dist = 1.5 * atr_val * sl_ratio
        tp_dist = sl_dist * tp_ratio
        
        result = {
            'pair': pair, 'direction': 'SHORT', 'entry_price': round(entry_price, 4),
            'stop_loss': round(entry_price + sl_dist, 4), 'tp1': round(entry_price - (tp_dist / 2), 4),
            'tp2': round(entry_price - tp_dist, 4), 'position_size': round(min(risk_usd / ((sl_dist/entry_price)*100/100), config.TOTAL_CAPITAL), 2),
            'signal_score': calculate_signal_score('SHORT'), **features_dict
        }

    return result

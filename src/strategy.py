# ---------------------------------------------------------
# FILE PATH: src/strategy.py (UPDATED WITH RISK GUARDRAILS & PROBABILITY AI)
# ---------------------------------------------------------
import os
import json
import sqlite3
import datetime
import config
from src import database, strategy_utils
import pandas as pd

def is_blocked_by_8h_filter(pair, current_direction):
    """
    بررسی دیتابیس لایو: اگر در ۸ ساعت گذشته سیگنالی برای این ارز و دقیقاً در همین جهت صادر شده باشد، 
    معامله جدید بلاک می‌شود.
    """
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
                    
                    diff_hours = (now - last_time).total_seconds() / 3600
                    
                    if diff_hours < 8:
                        return True
    except Exception as e:
        print(f"⚠️ خطا در بررسی فیلتر ۸ ساعته برای {pair}: {e}")
        
    return False

def generate_signal(df, pair, model=None):
    # دیکشنری پیش‌فرض امتیازات برای مواردی که دیتای کافی وجود ندارد
    default_scores = {
        'total_score': 0.0, 'ai_score': 0.0, 'rsi_score': 0.0, 'adx_score': 0.0, 'ema_score': 0.0,
        'direction': None
    }

    if df is None or len(df) < 200:
        return default_scores

    idx = len(df) - 1
    candle = df.iloc[idx]
    
    # خواندن پارامترهای اختصاصی ارز از best_params.json
    adx_thresh = config.ADX_THRESHOLD
    tp_ratio = 1.5
    sl_ratio = 1.0
    risk_multiplier = 1.0
    # لایه محافظتی: تعیین سقف ریسک (پیش‌فرض ۳ درصد از قیمت ورود)
    MAX_SL_PERCENT = getattr(config, 'MAX_SL_PERCENT', 0.03)
    
    # آستانه پیش‌فرض تایید هوش مصنوعی (مثلاً اگر احتمال بالای ۶۵٪ یا ۰.۶۵ بود)
    ai_threshold = 65.0
    
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
                ai_threshold = pair_params.get('ai_threshold', ai_threshold)
    except Exception as e:
        pass

    # --- پیاده‌سازی سیستم امتیازدهی هوشمند (بین ۰ تا ۱۰۰) ---
    
    current_adx = float(candle.get('feat_adx', 0))
    if current_adx >= adx_thresh:
        adx_score = min(100.0, 50.0 + ((current_adx - adx_thresh) * 2.5))
    else:
        adx_score = max(0.0, (current_adx / (adx_thresh + 1e-10)) * 50.0)

    current_rsi = float(candle.get('feat_rsi', 50))
    rsi_momentum = float(candle.get('feat_rsi_momentum', 0))
    if current_rsi > 50:
        rsi_score = min(100.0, 50.0 + (rsi_momentum * 5) if rsi_momentum > 0 else 50.0)
    else:
        rsi_score = min(100.0, 50.0 + (-rsi_momentum * 5) if rsi_momentum < 0 else 50.0)

    dev_val = abs(float(candle.get('feat_ema_deviation', 0)))
    ema_score = min(100.0, (dev_val / 5.0) * 100.0) if dev_val > 0 else 0.0

    ai_score = 0.0
    features_dict = {
        'feat_adx': current_adx,
        'feat_atr_percent': float(candle.get('feat_atr_percent', 0)),
        'feat_rsi': current_rsi,
        'feat_trend_line': float(candle.get('feat_trend_line', 0)),
        'feat_ema_deviation': float(candle.get('feat_ema_deviation', 0)),
        'feat_rsi_momentum': rsi_momentum,
        'feat_body_ratio': float(candle.get('feat_body_ratio', 0))
    }

    ai_approved = False
    if model is not None:
        try:
            # بررسی اینکه آیا مدل متد پیش‌بینی احتمالاتی دارد یا خیر
            if hasattr(model, 'predict_probability'):
                prob = model.predict_probability(pair, features_dict) # خروجی بین 0 تا 100 یا 0 تا 1
                if prob <= 1.0:
                    prob = prob * 100.0
                ai_score = prob
            else:
                # Fallback برای مدل‌های قدیمی گیت‌هاب که هنوز خروجی باینری دارند
                raw_pred = model.predict_signal(pair, features_dict)
                ai_score = 100.0 if raw_pred else 0.0
            
            # تاییدیه پویای هوش مصنوعی بر اساس آستانه تنظیم شده برای هر ارز
            if ai_score >= ai_threshold:
                ai_approved = True
        except Exception as e:
            print(f"❌ خطای بحرانی در مدل هوش مصنوعی {pair}: {e}")
            # ایمنی Fail-safe: اگر مدل خطا داد، معامله نکن
            return default_scores

    total_score = (ai_score * 0.40) + (adx_score * 0.20) + (rsi_score * 0.20) + (ema_score * 0.20)

    score_data = {
        'total_score': round(total_score, 2),
        'ai_score': round(ai_score, 2),
        'rsi_score': round(rsi_score, 2),
        'adx_score': round(adx_score, 2),
        'ema_score': round(ema_score, 2),
        'direction': None 
    }

    if total_score < 60.0 or database.get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
        return score_data

    last_swing_high = strategy_utils.find_last_swing(df, 'high', config.SWING_WINDOW)
    last_swing_low = strategy_utils.find_last_swing(df, 'low', config.SWING_WINDOW)

    if last_swing_high is None or last_swing_low is None:
        return score_data

    high_price = float(candle['High'])
    low_price = float(candle['Low'])
    atr_val = float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))

    # منطق ورود صعودی
    if high_price > last_swing_high and current_rsi > 50 and ai_approved:
        entry_price = last_swing_high
        if is_blocked_by_8h_filter(pair, "LONG"): return score_data
            
        risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0) * risk_multiplier
        # اعمال سقف ریسک (مینیمم فاصله ATR و سقف مجاز)
        sl_dist = min(1.5 * atr_val * sl_ratio, entry_price * MAX_SL_PERCENT)
        tp_dist = sl_dist * tp_ratio
        
        stop_loss = entry_price - sl_dist
        sl_percent = (sl_dist / entry_price) * 100
        
        max_allowed_size = config.TOTAL_CAPITAL * getattr(config, 'MAX_POSITION_SIZE_PCT', 0.10)
        position_size = min(risk_usd / (sl_percent / 100.0), max_allowed_size) if sl_percent > 0 else 0

        score_data.update({'pair': pair, 'direction': 'LONG', 'entry_price': round(entry_price, 4), 'stop_loss': round(stop_loss, 4), 'tp1': round(entry_price + (tp_dist / 2), 4), 'tp2': round(entry_price + tp_dist, 4), 'position_size': round(position_size, 2), **features_dict})
        return score_data
    
    # منطق ورود نزولی
    elif low_price < last_swing_low and current_rsi < 50 and ai_approved:
        entry_price = last_swing_low
        if is_blocked_by_8h_filter(pair, "SHORT"): return score_data
            
        risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0) * risk_multiplier
        # اعمال سقف ریسک (مینیمم فاصله ATR و سقف مجاز)
        sl_dist = min(1.5 * atr_val * sl_ratio, entry_price * MAX_SL_PERCENT)
        tp_dist = sl_dist * tp_ratio
        
        stop_loss = entry_price + sl_dist
        sl_percent = (sl_dist / entry_price) * 100
        
        max_allowed_size = config.TOTAL_CAPITAL * getattr(config, 'MAX_POSITION_SIZE_PCT', 0.10)
        position_size = min(risk_usd / (sl_percent / 100.0), max_allowed_size) if sl_percent > 0 else 0

        score_data.update({'pair': pair, 'direction': 'SHORT', 'entry_price': round(entry_price, 4), 'stop_loss': round(stop_loss, 4), 'tp1': round(entry_price - (tp_dist / 2), 4), 'tp2': round(entry_price - tp_dist, 4), 'position_size': round(position_size, 2), **features_dict})
        return score_data

    return score_data

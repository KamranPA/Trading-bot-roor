# ---------------------------------------------------------
# FILE PATH: src/strategy.py
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
    except Exception as e:
        pass

    # --- پیاده‌سازی سیستم امتیازدهی هوشمند (بین ۰ تا ۱۰۰) ---
    
    # ۱. امتیاز ADX (هرچه بالاتر از حد آستانه باشد امتیاز بیشتر تا سقف ۱۰۰)
    current_adx = float(candle.get('feat_adx', 0))
    if current_adx >= adx_thresh:
        adx_score = min(100.0, 50.0 + ((current_adx - adx_thresh) * 2.5))
    else:
        adx_score = max(0.0, (current_adx / (adx_thresh + 1e-10)) * 50.0)

    # ۲. امتیاز RSI (بررسی قدرت مومنتوم بازگشتی یا رونددار)
    current_rsi = float(candle.get('feat_rsi', 50))
    rsi_momentum = float(candle.get('feat_rsi_momentum', 0))
    # اگر RSI در مناطق اشباع همراه با شتاب موافق باشد امتیاز بالاتر می‌گیرد
    if current_rsi > 50:
        rsi_score = min(100.0, 50.0 + (rsi_momentum * 5) if rsi_momentum > 0 else 50.0)
    else:
        rsi_score = min(100.0, 50.0 + (-rsi_momentum * 5) if rsi_momentum < 0 else 50.0)

    # ۳. امتیاز انحراف میانگین (EMA Deviation)
    # انحراف‌های منطقی ترنددار امتیاز بالاتری می‌گیرند (بر اساس رفتار سوددهی لایه‌های عمیق)
    dev_val = abs(float(candle.get('feat_ema_deviation', 0)))
    ema_score = min(100.0, (dev_val / 5.0) * 100.0) if dev_val > 0 else 0.0

    # ۴. امتیاز هوش مصنوعی
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
            # 🛠️ اصلاح متد قدیمی از predict به predict_signal
            if model.predict_signal(pair, features_dict):
                ai_score = 100.0
                ai_approved = True
            else:
                ai_score = 0.0
        except Exception as e:
            print(f"خطا در مدل هوش مصنوعی {pair}: {e}")
            ai_score = 0.0

    # ۵. محاسبه امتیاز کل (وزنی)
    # هوش مصنوعی ۴۰٪ و اندیکاتورها هر کدام ۲۰٪ وزن دارند
    total_score = (ai_score * 0.40) + (adx_score * 0.20) + (rsi_score * 0.20) + (ema_score * 0.20)

    # ایجاد پکیج اطلاعات امتیازات جهت پاس دادن به دیتابیس برای پر شدن ستون‌های جدول لاگ
    score_data = {
        'total_score': round(total_score, 2),
        'ai_score': round(ai_score, 2),
        'rsi_score': round(rsi_score, 2),
        'adx_score': round(adx_score, 2),
        'ema_score': round(ema_score, 2),
        'direction': None # پیش‌فرض بدون پوزیشن است مگر اینکه شروط زیر تایید شوند
    }

    # --- بررسی شروط ورود به پوزیشن ---
    # شرط حد نصاب امتیاز برای ورود (مثلاً حداقل امتیاز ۶۰ از ۱۰۰)
    if total_score < 60.0:
        return score_data

    if database.get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
        return score_data

    last_swing_high = strategy_utils.find_last_swing(df, 'high', config.SWING_WINDOW)
    last_swing_low = strategy_utils.find_last_swing(df, 'low', config.SWING_WINDOW)

    if last_swing_high is None or last_swing_low is None:
        return score_data

    high_price = float(candle['High'])
    low_price = float(candle['Low'])
    
    is_bullish_momentum = current_rsi > 50
    is_bearish_momentum = current_rsi < 50

    # منطق ورود صعودی
    if high_price > last_swing_high and is_bullish_momentum and ai_approved:
        entry_price = last_swing_high
        
        if is_blocked_by_8h_filter(pair, "LONG"):
            return score_data
            
        risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0) * risk_multiplier
        atr_val = float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))
        sl_dist = 1.5 * atr_val * sl_ratio
        tp_dist = sl_dist * tp_ratio
        
        stop_loss = entry_price - sl_dist
        sl_percent = (sl_dist / entry_price) * 100
        position_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL) if sl_percent > 0 else 0

        score_data.update({
            'pair': pair, 
            'direction': 'LONG', 
            'entry_price': round(entry_price, 4),
            'stop_loss': round(stop_loss, 4), 
            'tp1': round(entry_price + (tp_dist / 2), 4),
            'tp2': round(entry_price + tp_dist, 4),
            'position_size': round(position_size, 2), 
            **features_dict
        })
        return score_data
    
    # منطق ورود نزولی
    elif low_price < last_swing_low and is_bearish_momentum and ai_approved:
        entry_price = last_swing_low
        
        if is_blocked_by_8h_filter(pair, "SHORT"):
            return score_data
            
        risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0) * risk_multiplier
        atr_val = float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))
        sl_dist = 1.5 * atr_val * sl_ratio
        tp_dist = sl_dist * tp_ratio
        
        stop_loss = entry_price + sl_dist
        sl_percent = (sl_dist / entry_price) * 100
        position_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL) if sl_percent > 0 else 0

        score_data.update({
            'pair': pair, 
            'direction': 'SHORT', 
            'entry_price': round(entry_price, 4),
            'stop_loss': round(stop_loss, 4), 
            'tp1': round(entry_price - (tp_dist / 2), 4),
            'tp2': round(entry_price - tp_dist, 4),
            'position_size': round(position_size, 2), 
            **features_dict
        })
        return score_data

    return score_data

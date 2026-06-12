# ---------------------------------------------------------
# FILE PATH: src/strategy.py (v8.2 - اصلاح شده برای ورود لحظه‌ای و بدون فیلتر حجم)
# ---------------------------------------------------------
import os
import json
import config
from src import database, strategy_utils
import pandas as pd

def is_blocked_by_8h_filter(pair):
    """
    بررسی اینکه آیا ارز مورد نظر توسط فیلتر ۸ ساعته مسدود شده است یا خیر.
    فعلاً به صورت پیش‌فرض False برمی‌گرداند تا ربات متوقف نشود.
    """
    return False 

def generate_signal(df, pair, model=None):
    # اطمینان از وجود دیتای کافی برای محاسبه اندیکاتورها (به ویژه EMA 200)
    if df is None or len(df) < 200:
        return None

    idx = len(df) - 1
    candle = df.iloc[idx]
    
    # ۱. فیلتر ۸ ساعته (بررسی مسدود بودن ارز)
    if is_blocked_by_8h_filter(pair):
        return None

    # ۲. مدیریت ریسک: کنترل سقف تعداد پوزیشن‌های باز
    if database.get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
        return None

    # --- خواندن پارامترهای اختصاصی ارز از best_params.json ---
    adx_thresh = config.ADX_THRESHOLD
    tp_ratio = 1.5  # ضریب پیش‌فرض سود
    sl_ratio = 1.0  # ضریب پیش‌فرض ضرر
    
    try:
        params_file = os.path.join(config.BASE_DIR, "best_params.json")
        if os.path.exists(params_file):
            with open(params_file, 'r') as f:
                all_params = json.load(f)
                
                # خواندن تنظیمات اختصاصی یا استفاده از DEFAULT به عنوان جایگزین
                pair_params = all_params.get(pair, all_params.get("DEFAULT", {}))
                
                adx_thresh = pair_params.get('adx_threshold', adx_thresh)
                tp_ratio = pair_params.get('tp_ratio', tp_ratio)
                sl_ratio = pair_params.get('sl_ratio', sl_ratio)
    except Exception as e:
        pass # در صورت بروز خطا، با همان مقادیر پیش‌فرض ادامه می‌دهد

    # ۳. فیلتر جهت‌گیری و شتاب روند کلان با حد آستانه اختصاصی این ارز
    if float(candle.get('feat_adx', 0)) < adx_thresh:
        return None

    # ۴. شناسایی سطوح سویینگ قیمتی
    last_swing_high = strategy_utils.find_last_swing(df, 'high', config.SWING_WINDOW)
    last_swing_low = strategy_utils.find_last_swing(df, 'low', config.SWING_WINDOW)

    if last_swing_high is None or last_swing_low is None:
        return None

    # ۵. آماده‌سازی ویژگی‌ها برای هوش مصنوعی (فیلترهای حجمی با توجه به تصمیم شما حذف شدند)
    features_dict = {
        'feat_adx': float(candle.get('feat_adx', 0)),
        'feat_atr_percent': float(candle.get('feat_atr_percent', 0)),
        'feat_rsi': float(candle.get('feat_rsi', 0)),
        'feat_trend_line': float(candle.get('feat_trend_line', 0)),
        'feat_ema_deviation': float(candle.get('feat_ema_deviation', 0)),
        'feat_rsi_momentum': float(candle.get('feat_rsi_momentum', 0)),
        'feat_body_ratio': float(candle.get('feat_body_ratio', 0))
    }

    # ۶. اعمال فیلتر هوش مصنوعی اختصاصی (Multi-Model)
    if model is not None:
        try:
            if not model.predict(pair, features_dict):
                return None
        except Exception as e:
            print(f"خطا در مدل هوش مصنوعی {pair}: {e}")
            pass

    # ۷. مشخص کردن قیمت‌های لحظه‌ای کندل فعلی برای منطق ورود شکست سطوح
    high_price = float(candle['High'])
    low_price = float(candle['Low'])
    
    # ۸. منطق شکست سطوح در لحظه برخورد (Intra-candle Breakout Logic)
    is_bullish_momentum = float(candle.get('feat_rsi', 50)) > 50
    is_bearish_momentum = float(candle.get('feat_rsi', 50)) < 50

    if high_price > last_swing_high and is_bullish_momentum:
        entry_price = last_swing_high  # قیمت ورود دقیقاً روی سطح شکست مقاومت
        
        # مدیریت سرمایه و محاسبه تارگت‌ها بر اساس ضرایب بهینه‌شده
        risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0)
        atr_val = float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))
        sl_dist = 1.5 * atr_val * sl_ratio
        tp_dist = sl_dist * tp_ratio
        
        stop_loss = entry_price - sl_dist
        sl_percent = (sl_dist / entry_price) * 100
        position_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL) if sl_percent > 0 else 0

        return {
            'pair': pair, 
            'direction': 'LONG', 
            'entry_price': round(entry_price, 4),
            'stop_loss': round(stop_loss, 4), 
            'tp1': round(entry_price + (tp_dist / 2), 4),
            'tp2': round(entry_price + tp_dist, 4),
            'position_size': round(position_size, 2), 
            **features_dict
        }
    
    elif low_price < last_swing_low and is_bearish_momentum:
        entry_price = last_swing_low  # قیمت ورود دقیقاً روی سطح شکست حمایت
        
        # مدیریت سرمایه و محاسبه تارگت‌ها بر اساس ضرایب بهینه‌شده
        risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0)
        atr_val = float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))
        sl_dist = 1.5 * atr_val * sl_ratio
        tp_dist = sl_dist * tp_ratio
        
        stop_loss = entry_price + sl_dist
        sl_percent = (sl_dist / entry_price) * 100
        position_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL) if sl_percent > 0 else 0

        return {
            'pair': pair, 
            'direction': 'SHORT', 
            'entry_price': round(entry_price, 4),
            'stop_loss': round(stop_loss, 4), 
            'tp1': round(entry_price - (tp_dist / 2), 4),
            'tp2': round(entry_price - tp_dist, 4),
            'position_size': round(position_size, 2), 
            **features_dict
        }

    return None

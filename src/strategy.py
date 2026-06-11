# ---------------------------------------------------------
# FILE PATH: src/strategy.py (v8.1 - Updated for Signal Control)
# ---------------------------------------------------------
import os
import json
import config
from src import database, strategy_utils
import pandas as pd
from src.telegram_bot import send_signal

def is_too_frequent(pair, direction):
    """
    بررسی اینکه آیا در ۳ کندل اخیر، سیگنالی در همان جهت صادر شده یا خیر.
    """
    # فراخوانی لیستی از آخرین سیگنال‌ها (فرض بر وجود این متد در database.py)
    last_signals = database.get_last_signals(pair, limit=3)
    for sig in last_signals:
        # اگر در ۳ رکورد آخر، سیگنالی با همین جهت وجود داشته باشد
        if sig.get('direction') == direction:
            return True
    return False

def handle_signal_output(signal_data):
    """
    ثبت در دیتابیس و ارسال تلگرام (مشروط به config)
    """
    # ۱. همیشه در دیتابیس ذخیره شود (جهت آموزش مدل)
    database.save_signal_advanced(signal_data)
    
    # ۲. ارسال تلگرام تنها در صورت فعال بودن در config
    if getattr(config, 'SEND_TELEGRAM_ALERTS', True):
        send_signal(signal_data)
    else:
        print(f"✅ سیگنال {signal_data['direction']} برای {signal_data['pair']} در دیتابیس ثبت شد (تلگرام غیرفعال است).")

def generate_signal(df, pair, model=None):
    if df is None or len(df) < 200:
        return None

    idx = len(df) - 1
    candle = df.iloc[idx]
    
    # ۱. فیلتر ۸ ساعته (جایگزین لاجیک قبلی)
    # توجه: می‌توانید در اینجا هم از is_too_frequent استفاده کنید یا لاجیک خودتان را بگذارید
    if is_too_frequent(pair, 'ANY'): # در صورت نیاز به بلاک کامل
        pass 

    # ۲. مدیریت ریسک: کنترل سقف تعداد پوزیشن‌های باز
    if database.get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
        return None

    # --- خواندن پارامترهای اختصاصی ارز ---
    adx_thresh = config.ADX_THRESHOLD
    tp_ratio, sl_ratio = 1.5, 1.0
    
    try:
        params_file = os.path.join(config.BASE_DIR, "best_params.json")
        if os.path.exists(params_file):
            with open(params_file, 'r') as f:
                all_params = json.load(f)
                pair_params = all_params.get(pair, all_params.get("DEFAULT", {}))
                adx_thresh = pair_params.get('adx_threshold', adx_thresh)
                tp_ratio = pair_params.get('tp_ratio', tp_ratio)
                sl_ratio = pair_params.get('sl_ratio', sl_ratio)
    except Exception: pass

    # ۳. فیلتر ADX
    if float(candle.get('feat_adx', 0)) < adx_thresh:
        return None

    # ۴. سطوح سویینگ
    last_swing_high = strategy_utils.find_last_swing(df, 'high', config.SWING_WINDOW)
    last_swing_low = strategy_utils.find_last_swing(df, 'low', config.SWING_WINDOW)
    if last_swing_high is None or last_swing_low is None: return None

    # ۵. ویژگی‌های هوش مصنوعی
    features_dict = {
        'feat_adx': float(candle.get('feat_adx', 0)),
        'feat_vol_ratio': float(candle.get('feat_vol_ratio', 0)),
        'feat_atr_percent': float(candle.get('feat_atr_percent', 0)),
        'feat_rsi': float(candle.get('feat_rsi', 0)),
        'feat_trend_line': float(candle.get('feat_trend_line', 0)),
        'feat_ema_deviation': float(candle.get('feat_ema_deviation', 0)),
        'feat_rsi_momentum': float(candle.get('feat_rsi_momentum', 0)),
        'feat_body_ratio': float(candle.get('feat_body_ratio', 0)),
        'feat_high_volume_session': float(candle.get('feat_high_volume_session', 0))
    }

    # ۶. مدل هوش مصنوعی
    if model is not None:
        try:
            if not model.predict(pair, features_dict): return None
        except Exception: pass

    # ۷. مدیریت سرمایه
    risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0)
    atr_val = float(candle.get('atr', 1.0))
    sl_dist = (1.5 * atr_val) * sl_ratio
    tp_dist = sl_dist * tp_ratio
    close_price = float(candle['Close'])
    
    if close_price <= 0: return None
    sl_percent = (sl_dist / close_price) * 100
    pos_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL) if sl_percent > 0 else 0

    # ۸. منطق شکست سطوح و ارسال خروجی
    is_bullish = float(candle.get('feat_rsi', 50)) > 50
    is_bearish = float(candle.get('feat_rsi', 50)) < 50

    if close_price > last_swing_high and is_bullish:
        if is_too_frequent(pair, 'LONG'): return None
        sig = {'pair': pair, 'direction': 'LONG', 'entry_price': round(close_price, 4), 
               'stop_loss': round(close_price - sl_dist, 4), 'tp1': round(close_price + (tp_dist/2), 4), 
               'tp2': round(close_price + tp_dist, 4), 'position_size': round(pos_size, 2), **features_dict}
        handle_signal_output(sig)
        return sig
    
    elif close_price < last_swing_low and is_bearish:
        if is_too_frequent(pair, 'SHORT'): return None
        sig = {'pair': pair, 'direction': 'SHORT', 'entry_price': round(close_price, 4), 
               'stop_loss': round(close_price + sl_dist, 4), 'tp1': round(close_price - (tp_dist/2), 4), 
               'tp2': round(close_price - tp_dist, 4), 'position_size': round(pos_size, 2), **features_dict}
        handle_signal_output(sig)
        return sig

    return None

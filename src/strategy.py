# ---------------------------------------------------------
# FILE PATH: src/strategy.py (نسخه نهایی، اصلاح تداخل آرگومان و دریافت هوشمند ورودی‌ها)
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
            # استخراج آخرین سیگنال همین ارز از دیتابیس
            cursor.execute(
                "SELECT direction, timestamp FROM signals WHERE symbol = ? ORDER BY id DESC LIMIT 1",
                (pair,)
            )
            last_signal = cursor.fetchone()

            if last_signal:
                last_direction, last_time_str = last_signal
                
                # بررسی شرط هم‌جهت بودن (مثلا لانگ بعد از لانگ)
                if last_direction == current_direction:
                    # تبدیل رشته زمانی دیتابیس (فرمت YYYY-MM-DD HH:MM:SS) به آبجکت زمان
                    clean_time_str = last_time_str.split('.')[0]
                    last_time = datetime.datetime.strptime(clean_time_str, '%Y-%m-%d %H:%M:%S')
                    now = datetime.datetime.utcnow() # SQLite از زمان UTC استفاده می‌کند
                    
                    # محاسبه اختلاف زمان به ساعت
                    diff_hours = (now - last_time).total_seconds() / 3600
                    
                    if diff_hours < 8:
                        return True # سیگنال مسدود است
    except Exception as e:
        print(f"⚠️ خطا در بررسی فیلتر ۸ ساعته برای {pair}: {e}")
        
    return False

def generate_signal(*args, **kwargs):
    """
    دریافت هوشمند ورودی‌ها: 
    جلوگیری از خطای TypeError در صورت جابه‌جا فرستاده شدن df و pair از فایل‌های دیگر.
    """
    df = None
    pair = None
    model = kwargs.get('model', None)

    # ۱. پردازش آرگومان‌های موقعیتی (تشخیص نوع داده)
    for arg in args:
        if isinstance(arg, pd.DataFrame):
            df = arg
        elif isinstance(arg, str):
            pair = arg
        elif hasattr(arg, 'predict_signal') or hasattr(arg, 'models'):
            model = arg

    # ۲. پردازش آرگومان‌های نامی (اگر پیدا نشده باشند)
    if df is None: df = kwargs.get('df', None)
    if pair is None: pair = kwargs.get('pair', None)

    # ۳. بررسی نهایی صحت داده‌ها
    if df is None or pair is None:
        return None

    # اطمینان از وجود دیتای کافی برای محاسبه اندیکاتورها (به ویژه EMA 200)
    if len(df) < 200:
        return None

    idx = len(df) - 1
    candle = df.iloc[idx]
    
    # ۲. مدیریت ریسک: کنترل سقف تعداد پوزیشن‌های باز
    try:
        if database.get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
            return None
    except Exception as e:
        print(f"⚠️ خطا در بررسی تعداد پوزیشن‌های باز: {e}")
        return None

    # --- خواندن پارامترهای اختصاصی ارز از best_params.json ---
    adx_thresh = config.ADX_THRESHOLD
    tp_ratio = 1.5  # ضریب پیش‌فرض سود
    sl_ratio = 1.0  # ضریب پیش‌فرض ضرر
    risk_multiplier = 1.0 # ضریب پیش‌فرض حجم معامله
    
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
                risk_multiplier = pair_params.get('risk_multiplier', risk_multiplier)
    except Exception as e:
        pass # در صورت بروز خطا، با همان مقادیر پیش‌فرض ادامه می‌دهد

    # ۳. فیلتر جهت‌گیری و شتاب روند کلان با حد آستانه اختصاصی این ارز
    # اصلاح لایه محافظتی استخراج داده برای جلوگیری از خطای KeyError یا مقدار None
    current_adx = candle.get('feat_adx') if 'feat_adx' in candle.index else candle.get('adx', 0)
    if pd.isna(current_adx) or float(current_adx) < adx_thresh:
        return None

    # ۴. شناسایی سطوح سویینگ قیمتی (یکپارچه‌سازی نام ستون‌ها با حروف کوچک)
    last_swing_high = strategy_utils.find_last_swing(df, 'high', config.SWING_WINDOW)
    last_swing_low = strategy_utils.find_last_swing(df, 'low', config.SWING_WINDOW)

    if last_swing_high is None or last_swing_low is None:
        return None

    # ۵. استخراج خودکار ویژگی‌ها با فیلتر ایمن جهت جلوگیری از تداخل آرگومان در تابع دیتابیس
    # با این فیلتر، کلمات کلیدی اصلی مثل pair یا direction هرگز دوبار فرستاده نمی‌شوند.
    reserved_keywords = {'pair', 'direction', 'entry_price', 'stop_loss', 'tp1', 'tp2', 'position_size'}
    features_dict = {}
    for col in df.columns:
        if col.startswith('feat_') and col not in reserved_keywords:
            val = candle[col]
            features_dict[col] = 0.0 if pd.isna(val) else float(val)

    if not features_dict:
        print(f"⚠️ هشدار: هیچ ویژگی یادگیری ماشین با پیشوند 'feat_' پیدا نشد.")

    # ۶. اعمال فیلتر هوش مصنوعی اختصاصی (Multi-Model / LightGBM)
    if model is not None and features_dict:
        try:
            # ارسال ویژگی‌های خودکار کشف شده به مغز مدل (TradingBrain)
            if not model.predict_signal(pair, features_dict):
                return None
        except Exception as e:
            print(f"❌ خطا در مدل هوش مصنوعی {pair}: {e}")
            pass

    # ۷. مشخص کردن قیمت‌های لحظه‌ای کندل فعلی برای منطق ورود شکست سطوح
    # اصلاح کلیدی: تغییر High و Low به حروف کوچک جهت هماهنگی با کل سیستم و دیتابیس صرافی
    high_price = float(candle['high']) if 'high' in candle.index else float(candle.get('High', 0))
    low_price = float(candle['low']) if 'low' in candle.index else float(candle.get('Low', 0))
    
    # ۸. منطق شکست سطوح در لحظه برخورد (Intra-candle Breakout Logic)
    current_rsi = candle.get('feat_rsi') if 'feat_rsi' in candle.index else candle.get('rsi', 50)
    if pd.isna(current_rsi):
        current_rsi = 50
        
    is_bullish_momentum = float(current_rsi) > 50
    is_bearish_momentum = float(current_rsi) < 50

    if high_price > last_swing_high and is_bullish_momentum:
        entry_price = last_swing_high  # قیمت ورود دقیقاً روی سطح شکست مقاومت
        
        # ---> چک کردن فیلتر ۸ ساعته دقیقا در لحظه تایید ورود <---
        if is_blocked_by_8h_filter(pair, "LONG"):
            return None
            
        # مدیریت سرمایه داینامیک با اعمال risk_multiplier
        risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0) * risk_multiplier
        atr_val = candle.get('atr') if 'atr' in candle.index else candle.get('feat_atr_percent', 1.0)
        if pd.isna(atr_val) or float(atr_val) <= 0:
            atr_val = 1.0
            
        sl_dist = 1.5 * float(atr_val) * sl_ratio
        tp_dist = sl_dist * tp_ratio
        
        stop_loss = entry_price - sl_dist
        sl_percent = (sl_dist / entry_price) * 100
        position_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL) if sl_percent > 0 else 0

        return {
            'pair': pair, 
            'direction': 'LONG', 
            'entry_price': round(float(entry_price), 4),
            'stop_loss': round(float(stop_loss), 4), 
            'tp1': round(float(entry_price + (tp_dist / 2)), 4),
            'tp2': round(float(entry_price + tp_dist), 4),
            'position_size': round(float(position_size), 2), 
            **features_dict  # اضافه کردن ایمن ویژگی‌ها بدون تداخل نام آرگومان
        }
    
    elif low_price < last_swing_low and is_bearish_momentum:
        entry_price = last_swing_low  # قیمت ورود دقیقاً روی سطح شکست حمایت
        
        # ---> چک کردن فیلتر ۸ ساعته دقیقا در لحظه تایید ورود <---
        if is_blocked_by_8h_filter(pair, "SHORT"):
            return None
            
        # مدیریت سرمایه داینامیک با اعمال risk_multiplier
        risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0) * risk_multiplier
        atr_val = candle.get('atr') if 'atr' in candle.index else candle.get('feat_atr_percent', 1.0)
        if pd.isna(atr_val) or float(atr_val) <= 0:
            atr_val = 1.0
            
        sl_dist = 1.5 * float(atr_val) * sl_ratio
        tp_dist = sl_dist * tp_ratio
        
        stop_loss = entry_price + sl_dist
        sl_percent = (sl_dist / entry_price) * 100
        position_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL) if sl_percent > 0 else 0

        return {
            'pair': pair, 
            'direction': 'SHORT', 
            'entry_price': round(float(entry_price), 4),
            'stop_loss': round(float(stop_loss), 4), 
            'tp1': round(float(entry_price - (tp_dist / 2)), 4),
            'tp2': round(float(entry_price - tp_dist), 4),
            'position_size': round(float(position_size), 2), 
            **features_dict  # اضافه کردن ایمن ویژگی‌ها بدون تداخل نام آرگومان
        }

    return None

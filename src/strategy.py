# src/strategy.py
# ماژول هسته استراتژی و صدور سیگنال (نسخه v1.2 - مدیریت ریسک چابک بر اساس ATR)

import pandas as pd
import config  # فراخوانی تنظیمات مرکزی برای حفظ ساختار ماژولار

def check_swing_high(df, index, window):
    """بررسی اینکه آیا کندل در این ایندکس، یک سقف سوئینگ معتبر است یا خیر"""
    if index < window or index >= len(df) - window:
        return False
    current_high = df.loc[index, 'High']
    # بررسی کندل‌های قبل و بعد
    for i in range(1, window + 1):
        if df.loc[index - i, 'High'] >= current_high or df.loc[index + i, 'High'] >= current_high:
            return False
    return True

def check_swing_low(df, index, window):
    """بررسی اینکه آیا کندل در این ایندکس، یک کف سوئینگ معتبر است یا خیر"""
    if index < window or index >= len(df) - window:
        return False
    current_low = df.loc[index, 'Low']
    # بررسی کندل‌های قبل و بعد
    for i in range(1, window + 1):
        if df.loc[index - i, 'Low'] <= current_low or df.loc[index + i, 'Low'] <= current_low:
            return False
    return True

def generate_signal(df, pair):
    """
    بررسی کندل لایو ۳۰ دقیقه‌ای برای صدور سیگنال به محض شکست سطوح سوئینگ ۴ ساعته
    محاسبه پویای تارگت‌ها و حد ضرر بر اساس ATR جهت چابک‌سازی و خروج چند روزه از پوزیشن
    """
    if df is None or len(df) < (config.SWING_WINDOW * 2 + 1):
        return None

    # آخرین کندل کاملاً بسته شده برای مبنای یاتاقان‌های سوئینگ
    last_closed_idx = len(df) - 2
    
    # انتخاب آخرین ردیف جدول (کندل لایو و در حال نوسان) برای ماشه ورود سریع
    live_candle_idx = len(df) - 1
    current_candle = df.iloc[live_candle_idx]
    
    # پیدا کردن آخرین سقف و کف سوئینگ معتبر در تاریخچه داده‌های بسته‌شده
    last_swing_high = None
    last_swing_low = None
    
    for idx in range(last_closed_idx, config.SWING_WINDOW, -1):
        if last_swing_high is None and check_swing_high(df, idx, config.SWING_WINDOW):
            last_swing_high = df.loc[idx, 'High']
        if last_swing_low is None and check_swing_low(df, idx, config.SWING_WINDOW):
            last_swing_low = df.loc[idx, 'Low']
        if last_swing_high is not None and last_swing_low is not None:
            break

    if last_swing_high is None or last_swing_low is None:
        return None

    # فیلترهای پایه: بررسی زنده بودن روند بازار در کندل لایو (ADX)
    if current_candle['ADX'] < config.ADX_THRESHOLD:
        return None # بازار رِنج است، خروج از تابع

    # بررسی شرط ورود برای معامله خرید (LONG) در لحظه شکست
    if current_candle['Close'] > last_swing_high and current_candle['Volume'] > current_candle['Volume_MA']:
        entry = current_candle['Close']
        atr = current_candle['ATR']
        
        # 🛠️ بازنویسی فرمول مدیریت ریسک بر اساس نَفَسِ لایو مارکت (ATR)
        sl = entry - (1.5 * atr)
        tp1 = entry + (1.5 * atr)
        tp2 = entry + (3.0 * atr) 
        
        return {
            'pair': pair,
            'direction': 'LONG',
            'entry_price': round(entry, 4),
            'stop_loss': round(sl, 4),
            'tp1': round(tp1, 4),
            'tp2': round(tp2, 4),
            'atr_value': round(atr, 4),
            'adx_value': round(current_candle['ADX'], 2)
        }

    # بررسی شرط ورود برای معامله فروش (SHORT) در لحظه شکست
    elif current_candle['Close'] < last_swing_low and current_candle['Volume'] > current_candle['Volume_MA']:
        entry = current_candle['Close']
        atr = current_candle['ATR']
        
        # 🛠️ بازنویسی فرمول مدیریت ریسک بر اساس نَفَسِ لایو مارکت (ATR)
        sl = entry + (1.5 * atr)
        tp1 = entry - (1.5 * atr)
        tp2 = entry - (3.0 * atr)
        
        return {
            'pair': pair,
            'direction': 'SHORT',
            'entry_price': round(entry, 4),
            'stop_loss': round(sl, 4),
            'tp1': round(tp1, 4),
            'tp2': round(tp2, 4),
            'atr_value': round(atr, 4),
            'adx_value': round(current_candle['ADX'], 2)
        }

    return None # هیچ شکستی در کندل لایو رخ نداده است

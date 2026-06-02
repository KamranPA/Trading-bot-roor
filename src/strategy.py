# src/strategy.py
import pandas as pd
import config

def check_swing_high(df, index, window):
    """بررسی تایید سقف سوئینگ بر اساس کندل‌های قبل و بعد"""
    if index < window or index >= len(df) - window:
        return False
    current_high = df.loc[index, 'High']
    # بررسی کندل‌های قبل و بعد در محدوده پنجره
    for i in range(1, window + 1):
        if df.loc[index - i, 'High'] > current_high or df.loc[index + i, 'High'] > current_high:
            return False
    return True

def check_swing_low(df, index, window):
    """بررسی تایید کف سوئینگ بر اساس کندل‌های قبل و بعد"""
    if index < window or index >= len(df) - window:
        return False
    current_low = df.loc[index, 'Low']
    for i in range(1, window + 1):
        if df.loc[index - i, 'Low'] < current_low or df.loc[index + i, 'Low'] < current_low:
            return False
    return True

def generate_signal(df, pair):
    """
    نسخه ارتقایافته: محاسبه نقاط سوئینگ تایید شده تاریخی و سنجش شکست توسط کندل لایو
    """
    if df is None or len(df) < (config.SWING_WINDOW * 2 + 1):
        return None

    live_candle_idx = len(df) - 1
    current_candle = df.iloc[live_candle_idx]
    
    # خروج سریع در صورت رِنج بودن بازار بر اساس ADX زنده
    if current_candle['ADX'] < config.ADX_THRESHOLD:
        return None

    last_swing_high = None
    last_swing_low = None
    
    # شروع جستجو از کندلی که فرآیند تایید سوئینگش (با توجه به پنجره) تکمیل شده است
    search_start_idx = len(df) - 1 - config.SWING_WINDOW
    
    for idx in range(search_start_idx, config.SWING_WINDOW, -1):
        if last_swing_high is None and check_swing_high(df, idx, config.SWING_WINDOW):
            last_swing_high = df.loc[idx, 'High']
        if last_swing_low is None and check_swing_low(df, idx, config.SWING_WINDOW):
            last_swing_low = df.loc[idx, 'Low']
        if last_swing_high is not None and last_swing_low is not None:
            break

    if last_swing_high is None or last_swing_low is None:
        return None

    # بررسی شرط ورود خرید (LONG) - شکست سقف سوئینگ + فیلتر حجم
    if current_candle['Close'] > last_swing_high and current_candle['Volume'] > current_candle['Volume_MA']:
        entry = current_candle['Close']
        atr = current_candle['ATR'] if current_candle['ATR'] > 0 else (entry * 0.02)
        
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

    # بررسی شرط ورود فروش (SHORT) - شکست کف سوئینگ + فیلتر حجم
    elif current_candle['Close'] < last_swing_low and current_candle['Volume'] > current_candle['Volume_MA']:
        entry = current_candle['Close']
        atr = current_candle['ATR'] if current_candle['ATR'] > 0 else (entry * 0.02)
        
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

    return None

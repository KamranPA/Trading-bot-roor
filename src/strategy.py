# src/strategy.py
# ماژول منطق استراتژی بر پایه شکست سطوح سوئینگ (Pivot) کالیبره شده با فیلتر روند و مدیریت ریسک داینامیک
# نسخه v4.1 - مجهز به خروجی غنی از داده‌های تکنیکال جهت آنالیز پس‌نگر مغز سیستم

import pandas as pd
import config
import database

def check_swing_high(df, index, window):
    """بررسی تایید سقف سوئینگ بر اساس کندل‌های قبل و بعد در پنجره مشخص شده"""
    if index < window or index >= len(df) - window:
        return False
    current_high = df.loc[index, 'High']
    
    # بررسی اینکه آیا سقف کندل جاری از تمام کندل‌های بازه پنجره بلندتر است یا خیر
    for i in range(1, window + 1):
        if df.loc[index - i, 'High'] > current_high or df.loc[index + i, 'High'] > current_high:
            return False
    return True

def check_swing_low(df, index, window):
    """بررسی تایید کف سوئینگ بر اساس کندل‌های قبل و بعد در پنجره مشخص شده"""
    if index < window or index >= len(df) - window:
        return False
    current_low = df.loc[index, 'Low']
    
    # بررسی اینکه آیا کف کندل جاری از تمام کندل‌های بازه پنجره پایین‌تر است یا خیر
    for i in range(1, window + 1):
        if df.loc[index - i, 'Low'] < current_low or df.loc[index + i, 'Low'] < current_low:
            return False
    return True

def generate_signal(df, pair):
    """
    سنجش شکست آخرین سطوح سوئینگ معتبر توسط کندل لایو بازار با فیلترهای ADX و میانگین حجم.
    خروجی حاوی متادیتای اندیکاتورها برای تغذیه و جراحی ماهانه مغز سیستم است.
    """
    # بررسی کفایت تعداد کندل‌ها برای محاسبات سوئینگ بر اساس تنظیمات پویا
    if df is None or len(df) < (config.SWING_WINDOW * 2 + 1):
        return None

    live_candle_idx = len(df) - 1
    current_candle = df.iloc[live_candle_idx]
    symbol = pair.split('/')[0]
    
    # فیلتر اول: خروج سریع در صورت رِنج و بی‌رمق بودن بازار بر اساس حد آستانه داینامیک ADX
    if current_candle['ADX'] < config.ADX_THRESHOLD:
        return None

    last_swing_high = None
    last_swing_low = None
    
    # نقطه شروع جستجوی معکوس (باید به اندازه پنجره از کندل لایو فاصله داشته باشد تا تاییدیه کامل باشد)
    search_start_idx = len(df) - 1 - config.SWING_WINDOW
    
    # حرکت معکوس در تاریخچه کندل‌ها برای پیدا کردن آخرین سقف و کف سوئینگ معتبر
    for idx in range(search_start_idx, config.SWING_WINDOW, -1):
        if last_swing_high is None and check_swing_high(df, idx, config.SWING_WINDOW):
            last_swing_high = df.loc[idx, 'High']
        if last_swing_low is None and check_swing_low(df, idx, config.SWING_WINDOW):
            last_swing_low = df.loc[idx, 'Low']
        
        # به محض پیدا شدن هر دو سطح، برای بهینه‌سازی سرعت لوپ را متوقف می‌کنیم
        if last_swing_high is not None and last_swing_low is not None:
            break

    if last_swing_high is None or last_swing_low is None:
        return None

    # 🟢 بررسی شرط ورود خرید (LONG) - شکست سقف سوئینگ + فیلتر تایید حجم معاملاتی فوق میانگین
    if current_candle['Close'] > last_swing_high and current_candle['Volume'] > current_candle['Volume_MA']:
        entry = current_candle['Close']
        atr = current_candle['ATR'] if current_candle['ATR'] > 0 else (entry * 0.02)
        
        # محاسبه حد ضرر و حد سودهای داینامیک متصل به فایل تنظیمات مرکزی
        sl = entry - (1.5 * atr)
        risk_distance = entry - sl
        
        tp1 = entry + (risk_distance * config.RISK_REWARD_TP1)
        tp2 = entry + (risk_distance * config.RISK_REWARD_TP1 * 2.0) # تارگت دوم با دو برابر ریسک به ریوارد اصلی
        
        # ترفند طلایی: گنجاندن متادیتای اندیکاتورها در متن لاگ دیتابیس برای کالبدشکافی مغز سیستم
        log_text = f"Signal LONG | Entry: {round(entry, 4)} | ADX: {round(current_candle['ADX'], 2)} | Vol_MA_Period: {config.VOLUME_MA_PERIOD}"
        database.log_scan(symbol, log_text)
        
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

    # 🔴 بررسی شرط ورود فروش (SHORT) - شکست کف سوئینگ + فیلتر تایید حجم معاملاتی فوق میانگین
    elif current_candle['Close'] < last_swing_low and current_candle['Volume'] > current_candle['Volume_MA']:
        entry = current_candle['Close']
        atr = current_candle['ATR'] if current_candle['ATR'] > 0 else (entry * 0.02)
        
        # محاسبه حد ضرر و حد سودهای داینامیک برای موقعیت فروش
        sl = entry + (1.5 * atr)
        risk_distance = sl - entry
        
        tp1 = entry - (risk_distance * config.RISK_REWARD_TP1)
        tp2 = entry - (risk_distance * config.RISK_REWARD_TP1 * 2.0)
        
        # گنجاندن متادیتای فنی برای آنالیزهای پس‌نگر هوش مصنوعی در انتهای ماه
        log_text = f"Signal SHORT | Entry: {round(entry, 4)} | ADX: {round(current_candle['ADX'], 2)} | Vol_MA_Period: {config.VOLUME_MA_PERIOD}"
        database.log_scan(symbol, log_text)
        
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

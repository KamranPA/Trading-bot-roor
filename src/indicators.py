# src/indicators.py
# ماژول محاسبات اندیکاتورهای تکنیکال (نسخه بهینه و مستقل)

import pandas as pd
import config

def calculate_indicators(df):
    """
    محاسبه کاملاً مستقل اندیکاتورهای ATR، ADX و میانگین حجم بدون نیاز به کتابخانه‌های سنگین خارجی
    """
    if df is None or df.empty or len(df) < 20:
        return None
    
    # --- ۱. محاسبه اندیکاتور ATR ---
    high_low = df['High'] - df['Low']
    high_close_prev = (df['High'] - df['Close'].shift(1)).abs()
    low_close_prev = (df['Low'] - df['Close'].shift(1)).abs()
    
    # پیدا کردن محدوده واقعی (True Range)
    tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
    # میانگین متحرک ساده برای ATR
    df['ATR'] = tr.rolling(window=config.ATR_PERIOD).mean()
    
    # --- ۲. محاسبه اندیکاتور ADX ---
    up_move = df['High'] - df['High'].shift(1)
    down_move = df['Low'].shift(1) - df['Low']
    
    plus_dm = (up_move > down_move) & (up_move > 0)
    plus_dm = up_move * plus_dm
    
    minus_dm = (down_move > up_move) & (down_move > 0)
    minus_dm = down_move * minus_dm
    
    # صاف کردن داده‌ها با میانگین متحرک
    tr_smoothed = tr.rolling(window=config.ADX_PERIOD).sum()
    plus_di = 100 * (plus_dm.rolling(window=config.ADX_PERIOD).sum() / tr_smoothed)
    minus_di = 100 * (minus_dm.rolling(window=config.ADX_PERIOD).sum() / tr_smoothed)
    
    # فرمول نهایی شاخص حرکت جهت‌دار (DX)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    # محاسبه نهایی ADX
    df['ADX'] = dx.rolling(window=config.ADX_PERIOD).mean()
    
    # --- ۳. محاسبه میانگین متحرک حجم ---
    df['Volume_MA'] = df['Volume'].rolling(window=config.VOLUME_MA_PERIOD).mean()
    
    # پر کردن فضاهای خالی اولیه با مقادیر صفر یا میانگین برای جلوگیری از ارور
    df.fillna(0, inplace=True)
    
    return df

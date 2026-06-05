# src/indicators.py
# بازگشت به نسخه پایدار v6.3 - هماهنگ با هسته اصلی ربات

import pandas as pd
import numpy as np

def calculate_indicators(df):
    """📊 محاسبه دقیق اندیکاتورهای تکنیکال و سنسورهای هوش مصنوعی با همپوشانی ۱۰۰٪ نام‌ها"""
    if df is None or df.empty or len(df) < 200:
        print(f"⚠️ دیتای کافی برای محاسبات تکنیکال وجود ندارد.")
        return df

    # ۱. محاسبه میانگین متحرک نمایی ۲۰۰ (EMA 200)
    df['ema_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    df['EMA_200'] = df['ema_200'] # همگام‌سازی برای توابع قدیمی
    
    # ۲. محاسبه شاخص قدرت نسبی (RSI 14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)
    df['feat_rsi'] = 100 - (100 / (1 + rs))
    df['feat_rsi'] = df['feat_rsi'].fillna(50.0)
    df['RSI'] = df['feat_rsi'] # همگام‌سازی برای توابع قدیمی

    # ۳. محاسبه میانگین محدوده واقعی (ATR 14) و درصد آن برای هوش مصنوعی
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    df['feat_atr_percent'] = (df['atr'] / df['Close']) * 100
    df['feat_atr_percent'] = df['feat_atr_percent'].fillna(0.0)
    df['ATR'] = df['atr'] # همگام‌سازی برای توابع قدیمی

    # ۴. محاسبه شاخص میانگین حرکت جهت‌دار (ADX 14)
    up_move = df['High'].diff()
    down_move = df['Low'].diff()
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    tr_smooth = tr.rolling(window=14).sum()
    plus_di = 100 * (pd.Series(plus_dm).rolling(window=14).sum() / (tr_smooth + 1e-10))
    minus_di = 100 * (pd.Series(minus_dm).rolling(window=14).sum() / (tr_smooth + 1e-10))
    
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)) * 100
    df['feat_adx'] = dx.rolling(window=14).mean().fillna(25.0)
    df['ADX'] = df['feat_adx'] # همگام‌سازی برای توابع قدیمی

    # ۵. محاسبه نسبت حجم معاملاتی (Volume Ratio) و میانگین متحرک حجم
    df['Volume_MA'] = df['Volume'].rolling(window=20).mean() # همگام‌سازی برای توابع قدیمی
    df['feat_vol_ratio'] = (df['Volume'] / (df['Volume_MA'] + 1e-10)).fillna(1.0)

    # ۶. تشخیص خط روند داینامیک نسبت به موقعیت قیمت با EMA 200
    df['feat_trend_line'] = np.where(df['Close'] > df['ema_200'], 1.0, 0.0)

    return df

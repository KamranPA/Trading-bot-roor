# ---------------------------------------------------------
# FILE NAME: indicators.py
# FILE PATH: /src/indicators.py
# ---------------------------------------------------------
import pandas as pd
import numpy as np
import config

def calculate_indicators(df):
    """📊 محاسبه سنسورهای هوشمند (با اصلاح قطعی باگ RSI و بدون فیلتر حجم)"""
    if df is None or df.empty or len(df) < 50:
        return df

    # ۱. محاسبات پایه قیمت
    df['ema_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # ۲. 🛠️ اصلاح قطعی و ریاضی باگ RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    # اصلاح شد: برای محاسبه میانگین ضررها فقط قیمت‌های منفی بررسی می‌شوند
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)
    df['feat_rsi'] = 100 - (100 / (1 + rs))
    
    # ۳. محاسبات ATR
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    df['feat_atr_percent'] = (df['atr'] / df['Close']) * 100
    
    # ۴. محاسبات ADX
    up_move = df['High'].diff()
    down_move = df['Low'].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr_smooth = tr.rolling(window=14).sum()
    plus_di = 100 * (pd.Series(plus_dm).rolling(window=14).sum() / (tr_smooth + 1e-10))
    minus_di = 100 * (pd.Series(minus_dm).rolling(window=14).sum() / (tr_smooth + 1e-10))
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)) * 100
    df['feat_adx'] = dx.rolling(window=14).mean().fillna(25.0)

    # ۵. سنسورهای حجمی (کاملا خنثی و بی‌اثر شدند تا نقش فیلتر نداشته باشند)
    # مقادیر ثابت داده شد تا دیتابیس ارور کمبود ستون ندهد
    df['feat_vol_ratio'] = 1.0 
    df['feat_high_volume_session'] = 0.0 
    
    # ۶. سنسورهای روند و کندل
    df['feat_trend_line'] = np.where(df['Close'] > df['ema_200'], 1.0, 0.0)
    df['feat_ema_deviation'] = ((df['Close'] - df['ema_200']) / df['ema_200']) * 100
    df['feat_rsi_momentum'] = df['feat_rsi'].diff().fillna(0.0)
    df['feat_body_ratio'] = (abs(df['Close'] - df['Open']) / (df['High'] - df['Low'] + 1e-10))

    return df.fillna(0.0)

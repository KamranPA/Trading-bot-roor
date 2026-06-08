# ---------------------------------------------------------
# FILE NAME: src/strategy_utils.py
# ---------------------------------------------------------
import pandas as pd
import numpy as np

def find_last_swing(df, window=5):
    """پیدا کردن آخرین نقطه سویینگ (High/Low) برای استراتژی"""
    if len(df) < window:
        return None
    
    # پیدا کردن آخرین سقف یا کف محلی
    last_high = df['high'].rolling(window=window, center=True).max().iloc[-1]
    last_low = df['low'].rolling(window=window, center=True).min().iloc[-1]
    
    return {"high": last_high, "low": last_low}

def calculate_adx(df, period=14):
    """محاسبه شاخص ADX برای فیلتر قدرت روند"""
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    tr1 = pd.DataFrame(df['high'] - df['low'])
    tr2 = pd.DataFrame(abs(df['high'] - df['close'].shift(1)))
    tr3 = pd.DataFrame(abs(df['low'] - df['close'].shift(1)))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(period).mean()
    
    return adx.iloc[-1]

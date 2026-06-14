# ---------------------------------------------------------
# FILE PATH: src/strategy_utils.py (Robust Version)
# ---------------------------------------------------------
import pandas as pd
import numpy as np

def find_last_swing(df, swing_type='high', window=3):
    try:
        if len(df) < window * 2: return None
        if swing_type == 'high':
            swing_series = df['High'].rolling(window=window*2+1, center=True).max()
            swings = df[df['High'] == swing_series]
            if not swings.empty: return float(swings.iloc[-1]['High'])
        elif swing_type == 'low':
            swing_series = df['Low'].rolling(window=window*2+1, center=True).min()
            swings = df[df['Low'] == swing_series]
            if not swings.empty: return float(swings.iloc[-1]['Low'])
        return None
    except: return None

def calculate_indicators(df):
    df = df.copy()
    # اطمینان از اینکه همه ستون‌ها عددی هستند
    df = df.apply(pd.to_numeric, errors='coerce').fillna(0)
    
    # اندیکاتورها
    df['feat_trend_line'] = np.where(df['Close'] > df['Close'].rolling(window=20).mean(), 1.0, 0.0)
    
    # فرمول ساده‌شده ADX برای جلوگیری از خطای سری‌های زمانی
    tr = df['High'] - df['Low']
    df['feat_adx'] = tr.rolling(window=14).mean().fillna(25.0)
    
    df['feat_atr_percent'] = (tr.rolling(window=14).mean() / df['Close']) * 100
    
    delta = df['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / (ema_down + 1e-10)
    df['feat_rsi'] = 100 - (100 / (1 + rs))
    
    ema_20 = df['Close'].ewm(span=20, adjust=False).mean()
    df['feat_ema_deviation'] = (df['Close'] - ema_20) / ema_20 * 100
    df['feat_rsi_momentum'] = df['feat_rsi'].diff().fillna(0)
    df['feat_body_ratio'] = abs(df['Close'] - df['Open']) / (df['High'] - df['Low'] + 0.0001)
    df['feat_high_volume_session'] = np.where((df['High'] - df['Low']) > (df['High'] - df['Low']).rolling(20).mean(), 1.0, 0.0)
    df['feat_vol_ratio'] = (df['High'] - df['Low']) / ((df['High'] - df['Low']).rolling(window=10).mean() + 1e-10)

    return df.fillna(0)

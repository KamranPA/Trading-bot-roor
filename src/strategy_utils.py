# FILE: src/strategy_utils.py
import pandas as pd
import numpy as np

def find_last_swing(df, swing_type='high', window=5):
    """
    پیدا کردن آخرین قله یا دره با استانداردسازی حروف.
    """
    try:
        df = df.copy()
        # اصلاح: تبدیل نام تمام ستون‌ها به حروف کوچک برای تطابق با دیتای صرافی
        df.columns = [c.lower() for c in df.columns]
        
        if len(df) < window * 2:
            return None
            
        if swing_type == 'high':
            # استفاده از نام‌های کوچک شده
            swing_series = df['high'].rolling(window=window*2+1, center=True).max()
            swings = df[df['high'] == swing_series]
            if not swings.empty:
                return float(swings.iloc[-1]['high'])
        elif swing_type == 'low':
            swing_series = df['low'].rolling(window=window*2+1, center=True).min()
            swings = df[df['low'] == swing_series]
            if not swings.empty:
                return float(swings.iloc[-1]['low'])
                
        return None
    except Exception as e:
        print(f"خطا در محاسبه Swing: {e}")
        return None

def calculate_indicators(df):
    """
    محاسبه ۹ فیلتر کلیدی بدون حذف حتی یک خط.
    """
    df = df.copy()
    # اصلاح: تبدیل نام تمام ستون‌ها به حروف کوچک برای جلوگیری از KeyError
    df.columns = [c.lower() for c in df.columns]
    
    # 1. Trend Line
    df['feat_trend_line'] = np.where(df['close'] > df['close'].rolling(window=20).mean(), 1.0, 0.0)
    
    # 2. ADX
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10) 
    df['feat_adx'] = 100 - (100 / (1 + rs))
    
    # 3. ATR Percent
    high_low = df['high'] - df['low']
    df['feat_atr_percent'] = (high_low.rolling(window=14).mean() / df['close']) * 100
    
    # 4. RSI
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / (ema_down + 1e-10)
    df['feat_rsi'] = 100 - (100 / (1 + rs))
    
    # 5. EMA Deviation
    ema_20 = df['close'].ewm(span=20, adjust=False).mean()
    df['feat_ema_deviation'] = (df['close'] - ema_20) / ema_20 * 100
    
    # 6. RSI Momentum
    df['feat_rsi_momentum'] = df['feat_rsi'].diff()
    
    # 7. Body Ratio
    df['feat_body_ratio'] = abs(df['close'] - df['open']) / (df['high'] - df['low'] + 0.0001)
    
    # 8. High Volume Session
    df['feat_high_volume_session'] = np.where((df['high'] - df['low']) > (df['high'] - df['low']).rolling(20).mean(), 1.0, 0.0)
    
    # 9. Volatility Ratio
    df['feat_vol_ratio'] = (df['high'] - df['low']) / ((df['high'] - df['low']).rolling(window=10).mean() + 1e-10)

    # پر کردن مقادیر خالی
    df.fillna(0, inplace=True)
    
    return df

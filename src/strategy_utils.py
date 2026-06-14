# ---------------------------------------------------------
# FILE PATH: src/strategy_utils.py
# ---------------------------------------------------------
import pandas as pd
import numpy as np

def find_last_swing(df, swing_type='high', window=5):
    """
    پیدا کردن آخرین قله (Swing High) یا دره (Swing Low) 
    برای تعیین نقاط مقاومت و حمایت استراتژی Breakout.
    """
    try:
        if len(df) < window * 2:
            return None
            
        if swing_type == 'high':
            # یافتن ماکزیمم محلی
            swing_series = df['High'].rolling(window=window*2+1, center=True).max()
            # پیدا کردن آخرین نقطه‌ای که ماکزیمم محلی با قیمت High خودش برابر است
            swings = df[df['High'] == swing_series]
            if not swings.empty:
                return float(swings.iloc[-1]['High'])
        elif swing_type == 'low':
            # یافتن مینیمم محلی
            swing_series = df['Low'].rolling(window=window*2+1, center=True).min()
            swings = df[df['Low'] == swing_series]
            if not swings.empty:
                return float(swings.iloc[-1]['Low'])
                
        return None
    except Exception as e:
        print(f"خطا در محاسبه Swing: {e}")
        return None

def calculate_indicators(df):
    """
    محاسبه ۹ فیلتر کلیدی برای سیستم هوشمند.
    فیلترهای حجم حذف شده‌اند و تمرکز بر قیمت و مومنتوم است.
    """
    df = df.copy()
    
    # 1. Trend Line (ساده‌سازی شده برای تشخیص روند کلی)
    df['feat_trend_line'] = np.where(df['Close'] > df['Close'].rolling(window=20).mean(), 1.0, 0.0)
    
    # 2. ADX (قدرت روند)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10) # جلوگیری از خطای تقسیم بر صفر
    df['feat_adx'] = 100 - (100 / (1 + rs))
    
    # 3. ATR Percent (نوسان‌پذیری)
    high_low = df['High'] - df['Low']
    df['feat_atr_percent'] = (high_low.rolling(window=14).mean() / df['Close']) * 100
    
    # 4. RSI (شاخص قدرت نسبی)
    delta = df['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / (ema_down + 1e-10)
    df['feat_rsi'] = 100 - (100 / (1 + rs))
    
    # 5. EMA Deviation (انحراف از میانگین - برای تشخیص پولبک)
    ema_20 = df['Close'].ewm(span=20, adjust=False).mean()
    df['feat_ema_deviation'] = (df['Close'] - ema_20) / ema_20 * 100
    
    # 6. RSI Momentum (شتاب RSI)
    df['feat_rsi_momentum'] = df['feat_rsi'].diff()
    
    # 7. Body Ratio (نسبت بدنه به سایه - قدرت خریدار/فروشنده)
    df['feat_body_ratio'] = abs(df['Close'] - df['Open']) / (df['High'] - df['Low'] + 0.0001)
    
    # 8. High Volume Session (تغییر ماهیت به نوسان قیمتی):
    df['feat_high_volume_session'] = np.where((df['High'] - df['Low']) > (df['High'] - df['Low']).rolling(20).mean(), 1.0, 0.0)
    
    # 9. Volatility Ratio (نسبت نوسان فعلی به میانگین)
    df['feat_vol_ratio'] = (df['High'] - df['Low']) / ((df['High'] - df['Low']).rolling(window=10).mean() + 1e-10)

    # پر کردن مقادیر خالی (NaN)
    df.fillna(0, inplace=True)
    
    return df

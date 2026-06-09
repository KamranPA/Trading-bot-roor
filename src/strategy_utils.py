# ---------------------------------------------------------
# FILE NAME: strategy_utils.py
# FILE PATH: /src/strategy_utils.py
# ---------------------------------------------------------
import pandas as pd
import numpy as np

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
    rs = gain / (loss + 1e-10)
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
    df['feat_ema_deviation'] = (df['Close'] - ema_20) / (ema_20 + 1e-10) * 100
    
    # 6. RSI Momentum (شتاب RSI)
    df['feat_rsi_momentum'] = df['feat_rsi'].diff()
    
    # 7. Body Ratio (نسبت بدنه به سایه - قدرت خریدار/فروشنده)
    df['feat_body_ratio'] = abs(df['Close'] - df['Open']) / (df['High'] - df['Low'] + 0.0001)
    
    # 8. High Volume Session (تغییر ماهیت به نوسان قیمتی):
    # به جای حجم، از دامنه تغییرات قیمت (Range) برای تشخیصِ اهمیت کندل استفاده می‌کنیم
    df['feat_high_volume_session'] = np.where((df['High'] - df['Low']) > (df['High'] - df['Low']).rolling(20).mean(), 1.0, 0.0)
    
    # 9. Volatility Ratio (نسبت نوسان فعلی به میانگین)
    df['feat_vol_ratio'] = (df['High'] - df['Low']) / ((df['High'] - df['Low']).rolling(window=10).mean() + 1e-10)

    # پر کردن مقادیر خالی (NaN)
    df.fillna(0, inplace=True)
    
    return df


def find_last_swing(df, swing_type, window=5):
    """
    🔍 شناسایی و استخراج آخرین سطوح مقاومتی و حمایتی (Swing High / Swing Low)
    برای منطق شکست در استراتژی معاملاتی Breakout
    """
    if df is None or len(df) < window + 1:
        return None
    
    try:
        # جستجو در کندل‌های اخیر (بدون احتساب کندل جاریِ در حال نوسان)
        if swing_type == 'high':
            return float(df['High'].iloc[-(window+1):-1].max())
        elif swing_type == 'low':
            return float(df['Low'].iloc[-(window+1):-1].min())
    except Exception:
        pass
        
    return None

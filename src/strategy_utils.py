# ---------------------------------------------------------
# FILE NAME: strategy_utils.py
# FILE PATH: /src/strategy_utils.py
# ---------------------------------------------------------
import pandas as pd
import numpy as np

def calculate_indicators(df):
    """
    📊 محاسبه فیلترهای قیمتی و مومنتوم سیستم هوشمند بدون فیلترهای حجم.
    تمام فاکتورهای وابسته به حجم معاملاتی حذف و با ساختار دیتابیس هماهنگ شده‌اند.
    """
    if df is None or df.empty or len(df) < 50:
        return df

    df = df.copy()

    # ۱. محاسبات میانگین متحرک نمایی (EMA 200) برای تشخیص جهت روند کلی
    df['ema_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    
    # ۲. محاسبه اندیکاتور RSI (دوره ۱۴)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-10)
    df['feat_rsi'] = 100 - (100 / (1 + rs))
    
    # ۳. محاسبه اندیکاتور ATR و درصد نوسان‌پذیری
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean().fillna(df['High'] - df['Low'])
    df['feat_atr_percent'] = (df['ATR'] / df['Close']) * 100
    
    # ۴. محاسبه دقیق اندیکاتور ADX برای سنجش قدرت روند بازار
    up_move = df['High'].diff()
    down_move = df['Low'].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr_smooth = tr.rolling(window=14).sum()
    plus_di = 100 * (pd.Series(plus_dm).rolling(window=14).sum() / (tr_smooth + 1e-10))
    minus_di = 100 * (pd.Series(minus_dm).rolling(window=14).sum() / (tr_smooth + 1e-10))
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)) * 100
    df['feat_adx'] = dx.rolling(window=14).mean().fillna(25.0)

    # ۵. ویژگی‌های هوش مصنوعی مبتنی بر روند، نوسان و مومنتوم قیمت
    df['feat_trend_line'] = np.where(df['Close'] > df['ema_200'], 1.0, 0.0)
    df['feat_ema_deviation'] = ((df['Close'] - df['ema_200']) / df['ema_200']) * 100
    df['feat_rsi_momentum'] = df['feat_rsi'].diff().fillna(0.0)
    df['feat_body_ratio'] = (abs(df['Close'] - df['Open']) / (df['High'] - df['Low'] + 1e-10))
    
    # نسبت نوسان فعلی به میانگین نوسانات گذشته (جایگزین نوسان حجم)
    df['feat_vol_ratio'] = (df['High'] - df['Low']) / ((df['High'] - df['Low']).rolling(window=10).mean() + 1e-10)

    return df.fillna(0.0)


def find_last_swing(df, swing_type, window=5):
    """
    🔍 ردیابی دقیق آخرین سقف (High) و کف (Low) بازار (Swing Points)
    این تابع برای استراتژی شکست سطوح (Breakout) حیاتی است.
    """
    try:
        if len(df) < (window * 2 + 1):
            return None
            
        idx = len(df) - 1
        
        for i in range(idx - window, window, -1):
            sub_section = df.iloc[i - window : i + window + 1]
            current_val = df.iloc[i]
            
            if swing_type.lower() == 'high':
                if current_val['High'] == sub_section['High'].max():
                    return float(current_val['High'])
                    
            elif swing_type.lower() == 'low':
                if current_val['Low'] == sub_section['Low'].min():
                    return float(current_val['Low'])
                    
        return None
    except Exception as e:
        print(f"❌ خطا در محاسبه نقاط Swing: {e}")
        return None

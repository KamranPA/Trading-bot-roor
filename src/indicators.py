import pandas as pd
import numpy as np

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    محاسبه دقیق اندیکاتورهای فنی و سنسورهای مورد نیاز مدل هوش مصنوعی.
    همراه با لایه محافظتی برای مدیریت داده‌های تهی (NaN).
    """
    if df is None or len(df) < 30:
        return pd.DataFrame()

    df = df.copy()
    
    try:
        # --- ۱. اندیکاتور RSI ---
        change = df['close'].diff()
        gain = change.mask(change < 0, 0)
        loss = -change.mask(change > 0, 0)
        average_gain = gain.rolling(window=14).mean()
        average_loss = loss.rolling(window=14).mean()
        # جلوگیری از تقسیم بر صفر
        rs = average_gain / average_loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50) # مقدار خنثی در صورت نبود داده

        # --- ۲. اندیکاتور ATR ---
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['atr'] = true_range.rolling(14).mean()
        # اصلاح قطعی برای برطرف کردن خطای FutureWarning پانداز
        df['atr'] = df['atr'].bfill().fillna(0)

        # --- ۳. اندیکاتور ADX ---
        upmove = df['high'].diff()
        downmove = df['low'].diff()
        plus_dm = np.where((upmove > downmove) & (upmove > 0), upmove, 0)
        minus_dm = np.where((downmove > upmove) & (downmove > 0), downmove, 0)
        
        tr_smooth = true_range.rolling(window=14).sum()
        plus_di = 100 * (pd.Series(plus_dm).rolling(window=14).sum() / tr_smooth.replace(0, np.nan))
        minus_di = 100 * (pd.Series(minus_dm).rolling(window=14).sum() / tr_smooth.replace(0, np.nan))
        
        dx = (np.abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
        df['adx'] = dx.rolling(window=14).mean()
        df['adx'] = df['adx'].fillna(20) # مقدار پیش‌فرض خنثی

        # --- ۴. میانگین‌های متحرک (MA) ---
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        df['sma_20'] = df['sma_20'].fillna(df['close'])
        df['sma_50'] = df['sma_50'].fillna(df['close'])

        # --- ۵. ویژگی‌های مشتق شده برای هوش مصنوعی ---
        df['pct_change'] = df['close'].pct_change().fillna(0)
        df['volatility'] = df['pct_change'].rolling(10).std().fillna(0)

        # حذف سطرهایی که هنوز داده کافی برای اندیکاتورها ندارند (اختیاری - با پر کردن مقادیر جایگزین شد)
        # برای اطمینان از عدم وجود NaN نهایی:
        df = df.ffill().bfill()
        
    except Exception as e:
        print(type(e).__name__, f"خطا در محاسبه اندیکاتورها: {str(e)}")
        
    return df

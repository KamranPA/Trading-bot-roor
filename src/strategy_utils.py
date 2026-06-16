# ---------------------------------------------------------
# FILE PATH: src/strategy_utils.py (v9.0 - Look-Ahead Bias Fixed & Cleaned)
# ---------------------------------------------------------
import pandas as pd
import numpy as np

def find_last_swing(df, swing_type='high', window=3):
    """
    پیدا کردن آخرین سقف یا کف سوینگ واقعی بدون نگاه به آینده (Anti Look-Ahead Bias).
    این متد کاملاً با ساختار بکتست و ربات لایو همخوانی دارد.
    """
    try:
        if len(df) < (window * 2 + 1): 
            return None
            
        # تبدیل ستون‌ها به آرایه برای افزایش سرعت پردازش روی گوشی و سرور
        highs = df['High'].to_numpy()
        lows = df['Low'].to_numpy()
        
        # حرکت از انتهای آرایه (آخرین کندل‌ها) به سمت گذشته برای پیدا کردن اولین سوینگ معتبر
        # از اندکس -window-1 شروع می‌کنیم چون خود کندل‌های آخر هنوز برای تایید سوینگ به کندل‌های بعدی نیاز دارند
        start_idx = len(df) - window - 1
        
        if swing_type == 'high':
            for i in range(start_idx, window - 1, -1):
                current_val = highs[i]
                # بررسی اینکه آیا مقدار فعلی از تمام کندل‌های بازه window قبل و بعد خود بزرگتر است یا خیر
                left_side = highs[i - window:i]
                right_side = highs[i + 1:i + window + 1]
                
                if np.all(current_val >= left_side) and np.all(current_val >= right_side):
                    return float(current_val)
                    
        elif swing_type == 'low':
            for i in range(start_idx, window - 1, -1):
                current_val = lows[i]
                # بررسی اینکه آیا مقدار فعلی از تمام کندل‌های بازه window قبل و بعد خود کوچکتر است یا خیر
                left_side = lows[i - window:i]
                right_side = lows[i + 1:i + window + 1]
                
                if np.all(current_val <= left_side) and np.all(current_val <= right_side):
                    return float(current_val)
                    
        return None
    except Exception as e:
        # برگشت امن در صورت رخ دادن هرگونه خطای غیرمنتظره در ساختار دیتامپ
        return None

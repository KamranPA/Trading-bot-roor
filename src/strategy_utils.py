# ---------------------------------------------------------
# FILE PATH: src/strategy_utils.py (v9.3 - Continuous Adaptive Window)
# ---------------------------------------------------------
import pandas as pd
import numpy as np
import config

def find_last_swing(df, swing_type='high', window=3):
    """
    پیدا کردن آخرین سقف یا کف سوینگ واقعی بدون نگاه به آینده (Anti Look-Ahead Bias).
    اصلاح شده با پنجره پویای پیوسته و فیلتر خطاهای شکست فیک در بازارهای رونددار.
    """
    try:
        dynamic_window = window
        if df is not None and 'atr' in df.columns and len(df) >= 20:
            # محاسبه نسبت نوسان فعلی به میانگین بلندمدت
            atr_ma = df['atr'].rolling(20).mean().iloc[-1]
            if atr_ma > 0:
                atr_ratio = df['atr'].iloc[-1] / atr_ma
                # اگر نوسانات بازار شدید شود، پنجره به صورت متناسب و پیوسته بزرگتر می‌شود (نه فقط ۱ واحد)
                if atr_ratio > 1.2:
                    dynamic_window = int(window * min(3.0, atr_ratio))

        if df is None or len(df) < (dynamic_window * 2 + 1): 
            # در صورتی که دیتا کافی نباشد، مقدار امن بر اساس آخرین کندل بازگردانده می‌شود
            if df is not None and len(df) > 0:
                return float(df['High'].iloc[-1]) if swing_type == 'high' else float(df['Low'].iloc[-1])
            return None
            
        # تبدیل ستون‌ها به آرایه برای افزایش سرعت پردازش روی گوشی و سرور گیت‌هاب
        highs = df['High'].to_numpy()
        lows = df['Low'].to_numpy()
        
        # حرکت از انتهای آرایه (آخرین کندل‌ها) به سمت گذشته برای پیدا کردن اولین سوینگ معتبر
        start_idx = len(df) - dynamic_window - 1
        
        if swing_type == 'high':
            for i in range(start_idx, dynamic_window - 1, -1):
                current_val = highs[i]
                # بررسی اینکه آیا مقدار فعلی از تمام کندل‌های بازه dynamic_window قبل و بعد خود بزرگتر است یا خیر
                left_side = highs[i - dynamic_window:i]
                right_side = highs[i + 1:i + dynamic_window + 1]
                
                if np.all(current_val >= left_side) and np.all(current_val >= right_side):
                    return float(current_val)
            
            # اصلاح Fallback: برای جلوگیری از اورفیت و ورود در اوج قیمت (شکست فیک)، 
            # به جای ماکسیمم کل دوره، None برمی‌گردانیم تا سیستم تا زمان شکل‌گیری سوینگ معتبر صبر کند.
            return None
                    
        elif swing_type == 'low':
            for i in range(start_idx, dynamic_window - 1, -1):
                current_val = lows[i]
                # بررسی اینکه آیا مقدار فعلی از تمام کندل‌های بازه dynamic_window قبل و بعد خود کوچکتر است یا خیر
                left_side = lows[i - dynamic_window:i]
                right_side = lows[i + 1:i + dynamic_window + 1]
                
                if np.all(current_val <= left_side) and np.all(current_val <= right_side):
                    return float(current_val)
            
            # اصلاح Fallback: جلوگیری از ورود فیک در ریزش‌های آبشاری بدون اصلاح قیمت
            return None
                    
        return None
    except Exception as e:
        # برگشت امن کنترل شده در صورت رخ دادن هرگونه خطای غیرمنتظره
        return None

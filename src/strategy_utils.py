# ---------------------------------------------------------
# FILE PATH: src/strategy_utils.py (v9.2 - Optimized & Robust)
# ---------------------------------------------------------
import pandas as pd
import numpy as np
import config

def find_last_swing(df, swing_type='high', window=3):
    """
    پیدا کردن آخرین سقف یا کف سوینگ واقعی بدون نگاه به آینده (Anti Look-Ahead Bias).
    اصلاح شده برای پایداری بیشتر در تایم‌فریم‌های مختلف.
    """
    try:
        # مدیریت هوشمند پنجره: اگر نوسان زیاد باشد (ATR بالا)، پنجره جستجو برای پیدا کردن سوینگ معتبر بزرگتر می‌شود
        dynamic_window = window
        if df is not None and 'atr' in df.columns:
            # اگر ATR اخیر نسبت به میانگین ATR بلندمدت بسیار بزرگ شده، پنجره را کمی بازتر کن تا سوینگ‌های واقعی‌تر پیدا شوند
            if df['atr'].iloc[-1] > df['atr'].rolling(20).mean().iloc[-1] * 1.5:
                dynamic_window = window + 1

        if df is None or len(df) < (dynamic_window * 2 + 1): 
            # در صورتی که دیتا کافی نباشد، مقدار امن بر اساس آخرین کندل بازگردانده می‌شود
            if df is not None and len(df) > 0:
                return float(df['High'].iloc[-1]) if swing_type == 'high' else float(df['Low'].iloc[-1])
            return None
            
        # تبدیل ستون‌ها به آرایه برای افزایش سرعت پردازش روی گوشی و سرور گیت‌هاب
        highs = df['High'].to_numpy()
        lows = df['Low'].to_numpy()
        
        # حرکت از انتهای آرایه (آخرین کندل‌ها) به سمت گذشته برای پیدا کردن اولین سوینگ معتبر
        # از اندکس -dynamic_window-1 شروع می‌کنیم
        start_idx = len(df) - dynamic_window - 1
        
        if swing_type == 'high':
            for i in range(start_idx, dynamic_window - 1, -1):
                current_val = highs[i]
                # بررسی اینکه آیا مقدار فعلی از تمام کندل‌های بازه dynamic_window قبل و بعد خود بزرگتر است یا خیر
                left_side = highs[i - dynamic_window:i]
                right_side = highs[i + 1:i + dynamic_window + 1]
                
                if np.all(current_val >= left_side) and np.all(current_val >= right_side):
                    return float(current_val)
            
            # Fallback: اگر سوینگ پیدا نشد، بالاترین قیمت در بازه اخیر را برگردان تا استراتژی کرش نکند
            return float(np.max(highs[-dynamic_window*2:]))
                    
        elif swing_type == 'low':
            for i in range(start_idx, dynamic_window - 1, -1):
                current_val = lows[i]
                # بررسی اینکه آیا مقدار فعلی از تمام کندل‌های بازه dynamic_window قبل و بعد خود کوچکتر است یا خیر
                left_side = lows[i - dynamic_window:i]
                right_side = lows[i + 1:i + dynamic_window + 1]
                
                if np.all(current_val <= left_side) and np.all(current_val <= right_side):
                    return float(current_val)
            
            # Fallback: اگر سوینگ پیدا نشد، پایین‌ترین قیمت در بازه اخیر را برگردان تا استراتژی کرش نکند
            return float(np.min(lows[-dynamic_window*2:]))
                    
        return None
    except Exception as e:
        # برگشت امن در صورت رخ دادن هرگونه خطای غیرمنتظره در ساختار دیتامپ
        if df is not None and len(df) > 0:
            return float(df['High'].iloc[-1]) if swing_type == 'high' else float(df['Low'].iloc[-1])
        return None

# FILE PATH: src/strategy_utils.py (v9.4 - case-insensitive columns)
import pandas as pd
import numpy as np
import config


def find_last_swing(df, swing_type='high', window=3):
    """
    پیدا کردن آخرین سقف یا کف سوینگ واقعی.
    اصلاح شده: سازگار با ستون‌های high/High (هر دو حالت)
    """
    try:
        # تشخیص نام ستون صحیح — indicators.py lowercase می‌کند
        if swing_type == 'high':
            col = 'High' if 'High' in df.columns else 'high'
        else:
            col = 'Low' if 'Low' in df.columns else 'low'

        atr_col = 'atr' if 'atr' in df.columns else ('ATR' if 'ATR' in df.columns else None)

        dynamic_window = window
        if atr_col and len(df) >= 20:
            atr_ma = df[atr_col].rolling(20).mean().iloc[-1]
            if atr_ma > 0:
                atr_ratio = df[atr_col].iloc[-1] / atr_ma
                if atr_ratio > 1.2:
                    dynamic_window = int(window * min(3.0, atr_ratio))

        if df is None or len(df) < (dynamic_window * 2 + 1):
            if df is not None and len(df) > 0:
                return float(df[col].iloc[-1])
            return None

        values = df[col].to_numpy()
        start_idx = len(df) - dynamic_window - 1

        if swing_type == 'high':
            for i in range(start_idx, dynamic_window - 1, -1):
                current_val = values[i]
                left_side  = values[i - dynamic_window:i]
                right_side = values[i + 1:i + dynamic_window + 1]
                if np.all(current_val >= left_side) and np.all(current_val >= right_side):
                    return float(current_val)
            return None

        elif swing_type == 'low':
            for i in range(start_idx, dynamic_window - 1, -1):
                current_val = values[i]
                left_side  = values[i - dynamic_window:i]
                right_side = values[i + 1:i + dynamic_window + 1]
                if np.all(current_val <= left_side) and np.all(current_val <= right_side):
                    return float(current_val)
            return None

        return None

    except Exception:
        return None

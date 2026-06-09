# File Path: src/strategy.py
import numpy as np
import pandas as pd
import logging
import config
from src import database, strategy_utils

def generate_signal(df, pair):
    if df is None or len(df) < 50:
        return None

    try:
        # 1. نرمال‌سازی اسامی ستون‌ها به حروف کوچک برای جلوگیری از خطای KeyError
        df.columns = [col.lower() for col in df.columns]
        
        # حالا با خیال راحت از حروف کوچک استفاده می‌کنیم
        idx = len(df) - 1
        candle = df.iloc[idx]
        
        # 2. استخراج داده‌ها با اسامی کوچک
        close_price = float(candle['close'])
        high_price = float(candle['high'])
        low_price = float(candle['low'])
        
        # 3. شناسایی آخرین قله و دره (با استفاده از تابع اصلی شما که قبلاً اصلاح کردیم)
        window = getattr(config, 'SWING_WINDOW', 5)
        last_swing_high = strategy_utils.find_last_swing(df, 'high', window)
        last_swing_low = strategy_utils.find_last_swing(df, 'low', window)

        if last_swing_high is None or last_swing_low is None:
            return None

        # 4. بقیه منطق استراتژی
        atr_value = float(candle.get('feat_atr_percent', 0.1)) * close_price / 100
        sl_dist = 1.5 * atr_value
        ema_200 = float(candle.get('ema_200', close_price))
        is_bullish = float(candle.get('feat_rsi', 50)) > 50

        if close_price > last_swing_high and close_price > ema_200 and is_bullish:
            return {
                'pair': pair, 'direction': 'LONG', 
                'entry_price': round(close_price, 4),
                'stop_loss': round(close_price - sl_dist, 4), 
                'tp1': round(close_price + (sl_dist * 1.5), 4),
                'tp2': round(close_price + (sl_dist * 2.5), 4)
            }
        
        # مشابه همین منطق برای SHORT اضافه شود...
            
    except Exception as e:
        logging.error(f"❌ خطا در پردازش استراتژی برای {pair}: {e}")

    return None

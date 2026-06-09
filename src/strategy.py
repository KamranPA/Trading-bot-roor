# File Path: src/strategy.py
import numpy as np
import pandas as pd
import logging
import config
from src import database, strategy_utils

def generate_signal(df, pair):
    """
    بررسی و تولید سیگنال بر اساس شکست سطوح (بدون فیلتر حجم)
    هماهنگ شده با main.py و strategy_utils.py
    """
    if df is None or len(df) < 50:
        return None

    try:
        idx = len(df) - 1
        candle = df.iloc[idx]
        
        # ۱. سقف تعداد پوزیشن‌های باز همزمان
        if database.get_open_positions_count() >= getattr(config, 'MAX_OPEN_POSITIONS', 15):
            return None

        # ۲. فیلتر قدرت روند (ADX) برای فیلتر بازارهای رنج
        adx_threshold = getattr(config, 'ADX_THRESHOLD', 25.0)
        if float(candle.get('feat_adx', 0)) < adx_threshold:
            return None

        # ۳. شناسایی آخرین قله و دره قیمتی با استفاده از تابع اصلی شما
        window = getattr(config, 'SWING_WINDOW', 5)
        last_swing_high = strategy_utils.find_last_swing(df, 'high', window)
        last_swing_low = strategy_utils.find_last_swing(df, 'low', window)

        if last_swing_high is None or last_swing_low is None:
            return None

        # ۴. استخراج ویژگی‌های معتبر قیمتی برای هوش مصنوعی (بدون فاکتورهای حجم)
        features = {
            'feat_adx': float(candle.get('feat_adx', 0)),
            'feat_rsi': float(candle.get('feat_rsi', 50)),
            'feat_trend_line': float(candle.get('feat_trend_line', 0)),
            'feat_ema_deviation': float(candle.get('feat_ema_deviation', 0)),
            'feat_rsi_momentum': float(candle.get('feat_rsi_momentum', 0)),
            'feat_body_ratio': float(candle.get('feat_body_ratio', 0)),
            'feat_vol_ratio': float(candle.get('feat_vol_ratio', 1.0)),
            'feat_atr_percent': float(candle.get('feat_atr_percent', 0))
        }

        # ۵. مدیریت سرمایه و محاسبات حد ضرر/سود
        close_price = float(candle['Close'])
        atr_value = float(candle['ATR'])
        
        if close_price <= 0: 
            return None
            
        sl_dist = 1.5 * atr_value

        # ۶. منطق شکست سطوح (Breakout Logic) همراه با تایید RSI و روند کلی (EMA200)
        is_bullish_momentum = float(candle.get('feat_rsi', 50)) > 50
        is_bearish_momentum = float(candle.get('feat_rsi', 50)) < 50
        ema_200 = float(candle.get('ema_200', close_price))

        # موقعیت خرید (LONG)
        if close_price > last_swing_high and close_price > ema_200 and is_bullish_momentum:
            return {
                'pair': pair, 
                'direction': 'LONG', 
                'entry_price': round(close_price, 4),
                'stop_loss': round(close_price - sl_dist, 4), 
                'tp1': round(close_price + sl_dist, 4),
                'tp2': round(close_price + (sl_dist * 2), 4),
                **features
            }
        
        # موقعیت فروش (SHORT)
        elif close_price < last_swing_low and close_price < ema_200 and is_bearish_momentum:
            return {
                'pair': pair, 
                'direction': 'SHORT', 
                'entry_price': round(close_price, 4),
                'stop_loss': round(close_price + sl_dist, 4), 
                'tp1': round(close_price - sl_dist, 4),
                'tp2': round(close_price - (sl_dist * 2), 4),
                **features
            }

    except Exception as e:
        logging.error(f"❌ خطا در پردازش استراتژی برای {pair}: {e}")

    return None

# File Path: src/strategy.py
import numpy as np
import pandas as pd
import logging
from src.strategy_utils import calculate_indicators
import config

def check_strategy(df):
    """
    بررسی دقیق استراتژی شکست سقف و کف داینامیک همراه با فیلترهای هوشمند
    خروجی: دیکشنری مشخصات سیگنال یا None
    """
    if df is None or len(df) < 50:
        return None

    try:
        # ۱. محاسبه تمام اندیکاتورهای مورد نیاز
        df = calculate_indicators(df)
        
        # دسترسی به آخرین کندل بسته شده (کندل یکی مانده به آخر برای جلوگیری از دیتای لایو و بی‌ثبات)
        last_row = df.iloc[-2]
        
        current_price = float(last_row['Close'])
        current_volume = float(last_row['Volume'])
        
        # استخراج اندیکاتورها
        rsi = float(last_row['RSI'])
        adx = float(last_row['ADX'])
        ema_200 = float(last_row['EMA_200'])
        atr = float(last_row['ATR'])
        
        # محاسبات انحراف‌ها جهت خروجی هوش مصنوعی
        ema_deviation = ((current_price - ema_200) / ema_200) * 100 if ema_200 else 0
        atr_percent = (atr / current_price) * 100 if current_price else 0

        # ۲. پیدا کردن سقف و کف‌های سووینگ اخیر (پنجره داینامیک)
        window = getattr(config, 'SWING_WINDOW', 5)
        
        # پیدا کردن بالاترین سقف و پایین‌ترین کف در کندلهای اخیر
        recent_highs = df.iloc[-(window*3):-2]['High'].tolist()
        recent_lows = df.iloc[-(window*3):-2]['Low'].tolist()
        
        last_swing_high = max(recent_highs) if recent_highs else current_price
        last_swing_low = min(recent_lows) if recent_lows else current_price

        # میانگین حجم برای تایید شکست
        volume_mean = df.iloc[-12:-2]['Volume'].mean()
        volume_confirmed = current_volume > (volume_mean * getattr(config, 'VOLUME_CONFIRMATION_RATIO', 1.1))

        # خواندن فیلتر ADX از کانفیگ مرکزی (اگر بهینه‌ساز آن را تغییر داده باشد)
        adx_threshold = getattr(config, 'ADX_THRESHOLD', 20.0) # کاهش پیش‌فرض از ۲۵ به ۲۰ برای سیگنال‌دهی سریع‌تر

        # 🟢 بررسی موقعیت خرید (LONG Signal)
        if current_price > last_swing_high and current_price > ema_200:
            if rsi > 50 and adx > adx_threshold:
                
                # محاسبه حد سود و ضرر داینامیک بر اساس ATR
                sl_dist = atr * 1.5
                stop_loss = current_price - sl_dist
                tp1 = current_price + (sl_dist * getattr(config, 'RISK_REWARD_TP1', 1.5))
                tp2 = current_price + (sl_dist * getattr(config, 'RISK_REWARD_TP2', 2.5))
                
                return {
                    'direction': 'LONG',
                    'entry_price': round(current_price, 4),
                    'stop_loss': round(stop_loss, 4),
                    'tp1': round(tp1, 4),
                    'tp2': round(tp2, 4),
                    'atr': round(atr_percent, 4),
                    'adx': round(adx, 2),
                    'rsi': round(rsi, 2),
                    'ema_diff': round(ema_deviation, 4)
                }

        # 🔴 بررسی موقعیت فروش (SHORT Signal)
        if current_price < last_swing_low and current_price < ema_200:
            if rsi < 50 and adx > adx_threshold:
                
                # محاسبه حد سود و ضرر داینامیک بر اساس ATR
                sl_dist = atr * 1.5
                stop_loss = current_price + sl_dist
                tp1 = current_price - (sl_dist * getattr(config, 'RISK_REWARD_TP1', 1.5))
                tp2 = current_price - (sl_dist * getattr(config, 'RISK_REWARD_TP2', 2.5))
                
                return {
                    'direction': 'SHORT',
                    'entry_price': round(current_price, 4),
                    'stop_loss': round(stop_loss, 4),
                    'tp1': round(tp1, 4),
                    'tp2': round(tp2, 4),
                    'atr': round(atr_percent, 4),
                    'adx': round(adx, 2),
                    'rsi': round(rsi, 2),
                    'ema_diff': round(ema_deviation, 4)
                }

    except Exception as e:
        logging.error(f"❌ خطا در محاسبه منطق استراتژی: {e}")
        
    return None

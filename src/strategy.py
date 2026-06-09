# File Path: src/strategy.py
import numpy as np
import pandas as pd
import logging
from src.strategy_utils import calculate_indicators
import config

def check_strategy(df):
    """
    بررسی استراتژی شکست سقف و کف داینامیک (بدون فیلتر حجم و کاملاً امن در برابر دیتای خالی)
    """
    # گام امنیتی: اگر دیتا وجود نداشت یا ناقص بود، بدون کرش کردن خارج شو
    if df is None or not isinstance(df, pd.DataFrame) or df.empty or len(df) < 50:
        return None

    try:
        # ۱. محاسبه اندیکاتورها از طریق ماژول کمکی شما
        df = calculate_indicators(df)
        
        # چک کردن مجدد برای اطمینان از اینکه خروجی لایبرری تحلیل هم خالی نیست
        if df is None or df.empty:
            return None
            
        # متصل کردن نام ستون‌ها به حروف کوچک برای ستون‌های استاندارد صرافی
        df.columns = [col.lower() for col in df.columns]
        
        # دسترسی به آخرین کندل بسته شده (یکی مانده به آخر)
        last_row = df.iloc[-2]
        current_price = float(last_row['close'])
        
        # استخراج اندیکاتورها با پشتیبانی هوشمند از حروف کوچک و بزرگ برای امنیت بالا
        rsi = float(last_row.get('rsi', last_row.get('RSI', 50.0)))
        adx = float(last_row.get('adx', last_row.get('ADX', 20.0)))
        ema_200 = float(last_row.get('ema_200', last_row.get('EMA_200', current_price)))
        atr = float(last_row.get('atr', last_row.get('ATR', 0.0)))
        
        # محاسبات فرعی تکنیکال برای ثبت در دیتابیس مانیتورینگ
        ema_deviation = ((current_price - ema_200) / ema_200) * 100 if ema_200 else 0
        atr_percent = (atr / current_price) * 100 if current_price else 0

        # ۲. پیدا کردن نقاط چرخش سقف و کف (Swing High / Swing Low)
        window = getattr(config, 'SWING_WINDOW', 5)
        recent_highs = df.iloc[-(window*3):-2]['high'].tolist()
        recent_lows = df.iloc[-(window*3):-2]['low'].tolist()
        
        last_swing_high = max(recent_highs) if recent_highs else current_price
        last_swing_low = min(recent_lows) if recent_lows else current_price

        # دریافت حد آستانه روند از تنظیمات
        adx_threshold = getattr(config, 'ADX_THRESHOLD', 25.0)

        # 🟢 بررسی موقعیت خرید (LONG) برای ارسال به تلگرام
        if current_price > last_swing_high and current_price > ema_200:
            if rsi > 50 and adx > adx_threshold:
                
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

        # 🔴 بررسی موقعیت فروش (SHORT) برای ارسال به تلگرام
        if current_price < last_swing_low and current_price < ema_200:
            if rsi < 50 and adx > adx_threshold:
                
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
        logging.error(f"❌ خطا در پردازش ریاضی استراتژی: {e}")
        
    return None

# ---------------------------------------------------------
# FILE NAME: strategy.py
# FILE PATH: /src/strategy.py
# ---------------------------------------------------------
import pandas as pd
import numpy as np
import config
from src import database, strategy_utils

def generate_signal(df, pair):
    if df is None or len(df) < 50:
        return None

    # محاسبه محلی ATR برای رفع قطعی خطای کلید 'ATR'
    df = df.copy()
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean().fillna(df['High'] - df['Low'])

    idx = len(df) - 1
    candle = df.iloc[idx]
    symbol = pair.split('/')[0]
    
    # ۱. مدیریت ریسک (فقط چک تعداد پوزیشن‌ها)
    if database.get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
        return None

    # ۲. فیلتر قدرت روند (ADX) برای جلوگیری از بازارهای رنج
    if float(candle.get('feat_adx', 0)) < config.ADX_THRESHOLD:
        return None

    # ۳. شناسایی سطوح Swing
    last_swing_high = strategy_utils.find_last_swing(df, 'high', config.SWING_WINDOW)
    last_swing_low = strategy_utils.find_last_swing(df, 'low', config.SWING_WINDOW)

    if last_swing_high is None or last_swing_low is None:
        return None

    # ۴. ویژگی‌های هوش مصنوعی
    features = {
        'feat_adx': float(candle.get('feat_adx', 0)),
        'feat_rsi': float(candle.get('feat_rsi', 50)),
        'feat_trend_line': float(candle.get('feat_trend_line', 0)),
        'feat_ema_deviation': float(candle.get('feat_ema_deviation', 0)),
        'feat_rsi_momentum': float(candle.get('feat_rsi_momentum', 0)),
        'feat_body_ratio': float(candle.get('feat_body_ratio', 0))
    }

    # ۵. مدیریت سرمایه و محاسبه حجم پوزیشن
    risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0)
    sl_dist = 1.5 * float(candle['ATR'])
    close_price = float(candle['Close'])
    
    if close_price <= 0: 
        return None
        
    sl_percent = (sl_dist / close_price) * 100
    position_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL) if sl_percent > 0 else 0

    # ۶. منطق شکست (Breakout Logic) به همراه تاییدیه مومنتوم RSI
    is_bullish_momentum = float(candle.get('feat_rsi', 50)) > 50
    is_bearish_momentum = float(candle.get('feat_rsi', 50)) < 50

    if close_price > last_swing_high and is_bullish_momentum:
        return {
            'pair': pair, 'direction': 'LONG', 'entry_price': round(close_price, 4),
            'stop_loss': round(close_price - sl_dist, 4), 
            'tp1': round(close_price + sl_dist, 4),
            'tp2': round(close_price + (sl_dist * 2), 4),
            'position_size': round(position_size, 2), **features
        }
    
    elif close_price < last_swing_low and is_bearish_momentum:
        return {
            'pair': pair, 'direction': 'SHORT', 'entry_price': round(close_price, 4),
            'stop_loss': round(close_price + sl_dist, 4), 
            'tp1': round(close_price - sl_dist, 4),
            'tp2': round(close_price - (sl_dist * 2), 4),
            'position_size': round(position_size, 2), **features
        }

    return None

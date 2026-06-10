# ---------------------------------------------------------
# FILE PATH: src/strategy.py
# ---------------------------------------------------------
import config
from src import database, strategy_utils

def generate_signal(df, pair):
    # اطمینان از وجود دیتای کافی برای محاسبه اندیکاتورها (به ویژه EMA 200)
    if df is None or len(df) < 200:
        return None

    idx = len(df) - 1
    candle = df.iloc[idx]
    
    # ۱. مدیریت ریسک: کنترل سقف تعداد پوزیشن‌های باز
    if database.get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
        return None

    # ۲. فیلتر جهت‌گیری و شتاب روند کلان (ADX)
    if float(candle.get('feat_adx', 0)) < config.ADX_THRESHOLD:
        return None

    # ۳. شناسایی سطوح سویینگ قیمتی (حمایت و مقاومت محلی)
    last_swing_high = strategy_utils.find_last_swing(df, 'high', config.SWING_WINDOW)
    last_swing_low = strategy_utils.find_last_swing(df, 'low', config.SWING_WINDOW)

    if last_swing_high is None or last_swing_low is None:
        return None

    # ۴. استخراج کامل ۹ ویژگی هوش مصنوعی هماهنگ با ساختار دیتابیس و مدل
    features = {
        'feat_adx': float(candle.get('feat_adx', 0)),
        'feat_vol_ratio': float(candle.get('feat_vol_ratio', 0)),
        'feat_atr_percent': float(candle.get('feat_atr_percent', 0)),
        'feat_rsi': float(candle.get('feat_rsi', 0)),
        'feat_trend_line': float(candle.get('feat_trend_line', 0)),
        'feat_ema_deviation': float(candle.get('feat_ema_deviation', 0)),
        'feat_rsi_momentum': float(candle.get('feat_rsi_momentum', 0)),
        'feat_body_ratio': float(candle.get('feat_body_ratio', 0)),
        'feat_high_volume_session': float(candle.get('feat_high_volume_session', 0))
    }

    # ۵. مدیریت سرمایه و محاسبه حجم پوزیشن بر اساس ریسک
    risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0)
    
    # رفع باگ حساسیت به حروف (استفاده از مقادیر محاسبه شده در indicators.py)
    sl_dist = 1.5 * float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))
    close_price = float(candle['Close'])
    
    if close_price <= 0: 
        return None
        
    sl_percent = (sl_dist / close_price) * 100
    position_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL) if sl_percent > 0 else 0

    # ۶. منطق شکست سطوح (Breakout Logic) و تاییدیه مومنتوم RSI
    is_bullish_momentum = float(candle.get('feat_rsi', 50)) > 50
    is_bearish_momentum = float(candle.get('feat_rsi', 50)) < 50

    # سیگنال خرید (Breakout صعودی)
    if close_price > last_swing_high and is_bullish_momentum:
        return {
            'pair': pair, 
            'direction': 'LONG', 
            'entry_price': round(close_price, 4),
            'stop_loss': round(close_price - sl_dist, 4), 
            'tp1': round(close_price + sl_dist, 4),
            'tp2': round(close_price + (sl_dist * 2), 4),
            'position_size': round(position_size, 2), 
            **features
        }
    
    # سیگنال فروش (Breakout نزولی)
    elif close_price < last_swing_low and is_bearish_momentum:
        return {
            'pair': pair, 
            'direction': 'SHORT', 
            'entry_price': round(close_price, 4),
            'stop_loss': round(close_price + sl_dist, 4), 
            'tp1': round(close_price - sl_dist, 4),
            'tp2': round(close_price - (sl_dist * 2), 4),
            'position_size': round(position_size, 2), 
            **features
        }

    return None

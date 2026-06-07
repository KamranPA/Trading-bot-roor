# ---------------------------------------------------------
# FILE PATH: /src/strategy.py
# ---------------------------------------------------------
import config
from src import database, strategy_utils

def generate_signal(df, pair):
    # بررسی کفایت داده‌ها برای محاسبه اندیکاتورها و سویینگ‌ها
    if df is None or len(df) < 500:
        return None

    # بررسی وجود ستون‌های حیاتی برای جلوگیری از خطای ساختاری
    if 'ATR' not in df.columns or 'Close' not in df.columns:
        return None

    idx = len(df) - 1
    candle = df.iloc[idx]
    symbol = pair.split('/')[0]
    
    # ۱. فیلتر مدیریت ریسک (اصلاح خطای عدم تعریف تابع)
    if database.get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
        database.log_scan(symbol, "No Signal (Max Positions)")
        return None

    # ۲. فیلترهای تکنیکال اصلی (۱۰ فاکتور)
    if float(candle['feat_adx']) < config.ADX_THRESHOLD or float(candle['feat_vol_confirm']) == 0:
        database.log_scan(symbol, "No Signal (Trend or Volume filter failed)")
        return None

    # ۳. شناسایی سطوح Swing (اصلاحی)
    last_swing_high = strategy_utils.find_last_swing(df, 'high', config.SWING_WINDOW)
    last_swing_low = strategy_utils.find_last_swing(df, 'low', config.SWING_WINDOW)

    # لایه محافظتی: اگر سطوح سویینگ به هر دلیلی یافت نشدند، از ایجاد موقعیت صرف‌نظر کن
    if last_swing_high is None or last_swing_low is None:
        return None

    # ۴. آماده‌سازی ویژگی‌های هوش مصنوعی (۱۰ فاکتور دقیق)
    features = {
        'feat_adx': float(candle['feat_adx']),
        'feat_vol_ratio': float(candle['feat_vol_ratio']),
        'feat_atr_percent': float(candle['feat_atr_percent']),
        'feat_rsi': float(candle['feat_rsi']),
        'feat_trend_line': float(candle['feat_trend_line']),
        'feat_ema_deviation': float(candle['feat_ema_deviation']),
        'feat_rsi_momentum': float(candle['feat_rsi_momentum']),
        'feat_body_ratio': float(candle['feat_body_ratio']),
        'feat_high_volume_session': float(candle['feat_high_volume_session']),
        'feat_vol_confirm': float(candle['feat_vol_confirm'])
    }

    # ۵. مدیریت سرمایه و ورود
    risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0)
    sl_dist = 1.5 * float(candle['ATR'])
    
    # لایه محافظتی برای جلوگیری از تقسیم بر صفر در صورتی که قیمت صفر باشد
    close_price = float(candle['Close'])
    if close_price <= 0:
        return None
        
    sl_percent = (sl_dist / close_price) * 100
    
    if sl_percent > 0:
        position_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL)
    else:
        position_size = 0

    # ۶. بررسی شکست سطوح (Breakout) و تولید سیگنال
    if close_price > last_swing_high:
        return {
            'pair': pair, 'direction': 'LONG', 'entry_price': round(close_price, 4),
            'stop_loss': round(close_price - sl_dist, 4), 
            'tp1': round(close_price + sl_dist, 4),
            'tp2': round(close_price + (sl_dist * 2), 4),
            'position_size': round(position_size, 2), **features
        }
    
    elif close_price < last_swing_low:
        return {
            'pair': pair, 'direction': 'SHORT', 'entry_price': round(close_price, 4),
            'stop_loss': round(close_price + sl_dist, 4), 
            'tp1': round(close_price - sl_dist, 4),
            'tp2': round(close_price - (sl_dist * 2), 4),
            'position_size': round(position_size, 2), **features
        }

    return None

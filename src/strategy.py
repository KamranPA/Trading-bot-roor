# ---------------------------------------------------------
# FILE PATH: /src/strategy.py
# ---------------------------------------------------------
import config
from src import database, strategy_utils # فرض بر این است که توابع swing در utils هستند

def generate_signal(df, pair):
    if df is None or len(df) < 500:
        return None

    idx = len(df) - 1
    candle = df.iloc[idx]
    symbol = pair.split('/')[0]
    
    # ۱. فیلتر مدیریت ریسک
    if get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
        database.log_scan(symbol, "No Signal (Max Positions)")
        return None

    # ۲. فیلترهای تکنیکال اصلی (۱۰ فاکتور)
    if float(candle['feat_adx']) < config.ADX_THRESHOLD or float(candle['feat_vol_confirm']) == 0:
        database.log_scan(symbol, "No Signal (Trend or Volume filter failed)")
        return None

    # ۳. شناسایی سطوح Swing (اصلاحی)
    last_swing_high = strategy_utils.find_last_swing(df, 'high', config.SWING_WINDOW)
    last_swing_low = strategy_utils.find_last_swing(df, 'low', config.SWING_WINDOW)

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
    sl_percent = (sl_dist / float(candle['Close'])) * 100
    position_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL)

    if candle['Close'] > last_swing_high:
        return {
            'pair': pair, 'direction': 'LONG', 'entry_price': round(float(candle['Close']), 4),
            'stop_loss': round(float(candle['Close']) - sl_dist, 4), 
            'tp1': round(float(candle['Close']) + sl_dist, 4),
            'tp2': round(float(candle['Close']) + (sl_dist * 2), 4),
            'position_size': round(position_size, 2), **features
        }
    
    elif candle['Close'] < last_swing_low:
        return {
            'pair': pair, 'direction': 'SHORT', 'entry_price': round(float(candle['Close']), 4),
            'stop_loss': round(float(candle['Close']) + sl_dist, 4), 
            'tp1': round(float(candle['Close']) - sl_dist, 4),
            'tp2': round(float(candle['Close']) - (sl_dist * 2), 4),
            'position_size': round(position_size, 2), **features
        }

    return None

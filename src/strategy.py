# ---------------------------------------------------------
# FILE PATH: /src/strategy.py
# ---------------------------------------------------------
import config
from src import database

def generate_signal(df, pair):
    if df is None or len(df) < (config.SWING_WINDOW * 2 + 1):
        return None

    current_idx = len(df) - 1
    candle = df.iloc[current_idx]
    symbol = pair.split('/')[0]
    
    # ۱. فیلتر مدیریت ریسک (سقف پوزیشن‌ها)
    if get_open_positions_count() >= config.MAX_OPEN_POSITIONS:
        database.log_scan(symbol, "No Signal (Max Positions Reached)")
        return None

    # ۲. فیلتر قدرت روند (ADX)
    if float(candle['feat_adx']) < config.ADX_THRESHOLD:
        database.log_scan(symbol, f"No Signal (Weak ADX: {round(candle['feat_adx'], 1)})")
        return None

    # ۳. فیلتر ۱۰ام (تایید حجم پویا - Volume Confirmation)
    # شرط: حجم باید حداقل ۱.۲ برابر میانگین باشد
    if float(candle['Volume']) < (float(candle['Volume_MA']) * config.VOLUME_CONFIRMATION_RATIO):
        database.log_scan(symbol, "No Signal (Low Volume Confirmation)")
        return None

    # شناسایی سطوح Swing
    # ... (کدهای check_swing_high/low به همان شکل قبل باقی می‌مانند) ...
    # (فرض بر این است که متغیرهای last_swing_high/low با همان منطق قبلی استخراج می‌شوند)

    # ۴. استخراج ۱۰ فاکتور نهایی برای هوش مصنوعی
    features = {
        'feat_adx': float(candle['feat_adx']),
        'feat_vol_ratio': float(candle['feat_vol_ratio']),
        'feat_atr_percent': float((candle['ATR'] / candle['Close']) * 100),
        'feat_rsi': float(candle['feat_rsi']),
        'feat_trend_line': float(candle['feat_trend_line']),
        'feat_ema_deviation': float(candle['feat_ema_deviation']),
        'feat_rsi_momentum': float(candle['feat_rsi_momentum']),
        'feat_body_ratio': float(candle['feat_body_ratio']),
        'feat_high_volume_session': float(candle['feat_high_volume_session']),
        'feat_vol_confirm': 1.0 # فاکتور جدیدِ تایید حجم
    }

    # محاسبه حجم معامله (Position Sizing)
    risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0)
    sl_dist = 1.5 * candle['ATR']
    sl_percent = (sl_dist / candle['Close']) * 100
    position_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL)

    # منطق ورود LONG/SHORT
    if candle['Close'] > last_swing_high:
        return {
            'pair': pair, 'direction': 'LONG', 'entry_price': round(candle['Close'], 4),
            'stop_loss': round(candle['Close'] - sl_dist, 4), 
            'tp1': round(candle['Close'] + sl_dist * config.RISK_REWARD_TP1, 4),
            'position_size': round(position_size, 2), **features
        }
    
    elif candle['Close'] < last_swing_low:
        return {
            'pair': pair, 'direction': 'SHORT', 'entry_price': round(candle['Close'], 4),
            'stop_loss': round(candle['Close'] + sl_dist, 4), 
            'tp1': round(candle['Close'] - sl_dist * config.RISK_REWARD_TP1, 4),
            'position_size': round(position_size, 2), **features
        }

    return None

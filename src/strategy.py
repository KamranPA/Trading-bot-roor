# ---------------------------------------------------------
# FILE PATH: src/strategy.py
# ---------------------------------------------------------
import config
from src import database, strategy_utils
import pandas as pd # اطمینان از وارد کردن پانداز برای کار با دیتافریم

def generate_signal(df, pair, model=None):
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

    # ۳. شناسایی سطوح سویینگ قیمتی
    last_swing_high = strategy_utils.find_last_swing(df, 'high', config.SWING_WINDOW)
    last_swing_low = strategy_utils.find_last_swing(df, 'low', config.SWING_WINDOW)

    if last_swing_high is None or last_swing_low is None:
        return None

    # ۴. آماده‌سازی ویژگی‌ها
    features_dict = {
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

    # ۵. اعمال فیلتر هوش مصنوعی (در صورت وجود مدل)
    if model is not None:
        # استخراج همان ۶ ویژگی مورد نظر برای مدل
        features_df = pd.DataFrame([features_dict])
        subset = features_df[['feat_adx', 'feat_rsi', 'feat_trend_line', 
                              'feat_ema_deviation', 'feat_rsi_momentum', 'feat_body_ratio']]
        
        prediction = model.predict(subset)
        
        # اگر پیش‌بینی مدل منفی (۰) بود، سیگنال صادر نشود
        if prediction[0] == 0:
            return None

    # ۶. مدیریت سرمایه
    risk_usd = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0)
    sl_dist = 1.5 * float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))
    close_price = float(candle['Close'])
    
    if close_price <= 0: 
        return None
        
    sl_percent = (sl_dist / close_price) * 100
    position_size = min(risk_usd / (sl_percent / 100.0), config.TOTAL_CAPITAL) if sl_percent > 0 else 0

    # ۷. منطق شکست سطوح (Breakout Logic)
    is_bullish_momentum = float(candle.get('feat_rsi', 50)) > 50
    is_bearish_momentum = float(candle.get('feat_rsi', 50)) < 50

    if close_price > last_swing_high and is_bullish_momentum:
        return {
            'pair': pair, 
            'direction': 'LONG', 
            'entry_price': round(close_price, 4),
            'stop_loss': round(close_price - sl_dist, 4), 
            'tp1': round(close_price + sl_dist, 4),
            'tp2': round(close_price + (sl_dist * 2), 4),
            'position_size': round(position_size, 2), 
            **features_dict
        }
    
    elif close_price < last_swing_low and is_bearish_momentum:
        return {
            'pair': pair, 
            'direction': 'SHORT', 
            'entry_price': round(close_price, 4),
            'stop_loss': round(close_price + sl_dist, 4), 
            'tp1': round(close_price - sl_dist, 4),
            'tp2': round(close_price - (sl_dist * 2), 4),
            'position_size': round(position_size, 2), 
            **features_dict
        }

    return None

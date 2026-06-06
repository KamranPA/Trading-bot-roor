# src/strategy.py
# نسخه نهایی v7.1 - مجهز به لایه محاسباتی حجم‌گذاری پویا و فیلتر سقف پوزیشن‌های باز

import pandas as pd
import sqlite3
import config
from src import database

def get_open_positions_count():
    """🛡️ شمارش تعداد پوزیشن‌های باز فعلی در دیتابیس جهت کنترل ریسک کل حساب"""
    try:
        conn = sqlite3.connect(database.DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0

def check_swing_high(df, index, window):
    if index < window or index >= len(df) - window:
        return False
    current_high = df.loc[index, 'High']
    for i in range(1, window + 1):
        if df.loc[index - i, 'High'] > current_high or df.loc[index + i, 'High'] > current_high:
            return False
    return True

def check_swing_low(df, index, window):
    if index < window or index >= len(df) - window:
        return False
    current_low = df.loc[index, 'Low']
    for i in range(1, window + 1):
        if df.loc[index - i, 'Low'] < current_low or df.loc[index + i, 'Low'] < current_low:
            return False
    return True

def generate_signal(df, pair):
    if df is None or len(df) < (config.SWING_WINDOW * 2 + 1):
        return None

    live_candle_idx = len(df) - 1
    current_candle = df.iloc[live_candle_idx]
    symbol = pair.split('/')[0]
    
    # 🟢 ثبت لاگ زنده در هر بار اسکن برای مطمئن شدن از کارکرد صحیح ربات
    database.log_scan(symbol, "Scanning market...")

    # 🛡️ بررسی فیلتر مدیریت سرمایه: سقف پوزیشن‌های باز هم‌زمان
    open_count = get_open_positions_count()
    if open_count >= config.MAX_OPEN_POSITIONS:
        database.log_scan(symbol, f"No Signal (Max Open Positions Limit Reached: {open_count})")
        return None

    if current_candle['ADX'] < config.ADX_THRESHOLD:
        database.log_scan(symbol, f"No Signal (Weak ADX: {round(current_candle['ADX'], 1)})")
        return None

    last_swing_high = None
    last_swing_low = None
    search_start_idx = len(df) - 1 - config.SWING_WINDOW
    
    for idx in range(search_start_idx, config.SWING_WINDOW, -1):
        if last_swing_high is None and check_swing_high(df, idx, config.SWING_WINDOW):
            last_swing_high = df.loc[idx, 'High']
        if last_swing_low is None and check_swing_low(df, idx, config.SWING_WINDOW):
            last_swing_low = df.loc[idx, 'Low']
        if last_swing_high is not None and last_swing_low is not None:
            break

    if last_swing_high is None or last_swing_low is None:
        database.log_scan(symbol, "No Signal (Levels Not Found)")
        return None

    # 🧮 استخراج ۹ فاکتور بومی هوش مصنوعی
    entry_est = float(current_candle['Close'])
    atr_val = current_candle['ATR'] if current_candle['ATR'] > 0 else (entry_est * 0.02)
    atr_percent = float((atr_val / entry_est) * 100)
    vol_ratio = float(current_candle['feat_vol_ratio'])
    adx_val = float(current_candle['feat_adx'])
    rsi_val = float(current_candle['feat_rsi'])
    trend_line = float(current_candle['feat_trend_line'])
    ema_deviation = float(current_candle['feat_ema_deviation'])
    rsi_momentum = float(current_candle['feat_rsi_momentum'])
    body_ratio = float(current_candle['feat_body_ratio'])
    high_volume_session = float(current_candle['feat_high_volume_session'])

    # 💰 فرمول طلایی مدیریت سرمایه پویا (Dynamic Position Sizing)
    allowed_loss_amount = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0)

    # شرط خرید (LONG)
    if current_candle['Close'] > last_swing_high and current_candle['Volume'] > current_candle['Volume_MA']:
        sl = entry_est - (1.5 * atr_val)
        risk_dist = entry_est - sl
        
        # محاسبه درصد ریسک معامله و حجم مجاز به دلار
        sl_percent = (risk_dist / entry_est) * 100.0
        position_size = allowed_loss_amount / (sl_percent / 100.0)
        # محدود کردن حجم به حداکثر کل سرمایه جهت جلوگیری از خطای اهرم ناخواسته
        position_size = min(position_size, config.TOTAL_CAPITAL)

        tp1 = entry_est + (risk_dist * config.RISK_REWARD_TP1)
        tp2 = entry_est + (risk_dist * config.RISK_REWARD_TP1 * 2.0)
        
        database.log_scan(symbol, f"🔥 Signal LONG | Size: ${round(position_size, 1)}")
        
        return {
            'pair': pair, 'direction': 'LONG', 'entry_price': round(entry_est, 4),
            'stop_loss': round(sl, 4), 'tp1': round(tp1, 4), 'tp2': round(tp2, 4),
            'position_size': round(position_size, 2), 'sl_percent': round(sl_percent, 2),
            'feat_adx': round(adx_val, 2), 'feat_vol_ratio': round(vol_ratio, 2), 'feat_atr_percent': round(atr_percent, 2),
            'feat_rsi': round(rsi_val, 2), 'feat_trend_line': trend_line,
            'feat_ema_deviation': round(ema_deviation, 2), 'feat_rsi_momentum': round(rsi_momentum, 2),
            'feat_body_ratio': round(body_ratio, 2), 'feat_high_volume_session': high_volume_session
        }

    # شرط فروش (SHORT)
    elif current_candle['Close'] < last_swing_low and current_candle['Volume'] > current_candle['Volume_MA']:
        sl = entry_est + (1.5 * atr_val)
        risk_dist = sl - entry_est
        
        # محاسبه درصد ریسک معامله و حجم مجاز به دلار
        sl_percent = (risk_dist / entry_est) * 100.0
        position_size = allowed_loss_amount / (sl_percent / 100.0)
        position_size = min(position_size, config.TOTAL_CAPITAL)

        tp1 = entry_est - (risk_dist * config.RISK_REWARD_TP1)
        tp2 = entry_est - (risk_dist * config.RISK_REWARD_TP1 * 2.0)
        
        database.log_scan(symbol, f"🔥 Signal SHORT | Size: ${round(position_size, 1)}")
        
        return {
            'pair': pair, 'direction': 'SHORT', 'entry_price': round(entry_est, 4),
            'stop_loss': round(sl, 4), 'tp1': round(tp1, 4), 'tp2': round(tp2, 4),
            'position_size': round(position_size, 2), 'sl_percent': round(sl_percent, 2),
            'feat_adx': round(adx_val, 2), 'feat_vol_ratio': round(vol_ratio, 2), 'feat_atr_percent': round(atr_percent, 2),
            'feat_rsi': round(rsi_val, 2), 'feat_trend_line': trend_line,
            'feat_ema_deviation': round(ema_deviation, 2), 'feat_rsi_momentum': round(rsi_momentum, 2),
            'feat_body_ratio': round(body_ratio, 2), 'feat_high_volume_session': high_volume_session
        }

    database.log_scan(symbol, "No Signal (Conditions Not Met)")
    return None

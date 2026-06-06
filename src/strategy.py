# src/strategy.py
import pandas as pd
import sqlite3
import config
from src import database

def get_open_positions_count():
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
    if index < window or index >= len(df) - window: return False
    current_high = df.loc[index, 'High']
    for i in range(1, window + 1):
        if df.loc[index - i, 'High'] > current_high or df.loc[index + i, 'High'] > current_high:
            return False
    return True

def check_swing_low(df, index, window):
    if index < window or index >= len(df) - window: return False
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
    
    database.log_scan(symbol, "Scanning market...")

    # محدودیت تعداد پوزیشن از اینجا حذف شد تا سیگنال‌ها برای مدیریت در main.py تولید شوند
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

    entry_est = float(current_candle['Close'])
    atr_val = current_candle['ATR'] if current_candle['ATR'] > 0 else (entry_est * 0.02)
    
    # محاسبه حجم (Dynamic Sizing)
    allowed_loss_amount = config.TOTAL_CAPITAL * (config.RISK_PERCENT / 100.0)
    risk_dist = atr_val * 1.5 
    sl_percent = (risk_dist / entry_est) * 100.0
    position_size = min(allowed_loss_amount / (sl_percent / 100.0), config.TOTAL_CAPITAL)

    if current_candle['Close'] > last_swing_high and current_candle['Volume'] > current_candle['Volume_MA']:
        return {
            'pair': pair, 'direction': 'LONG', 'entry_price': round(entry_est, 4),
            'stop_loss': round(entry_est - risk_dist, 4), 'tp1': round(entry_est + (risk_dist * config.RISK_REWARD_TP1), 4),
            'tp2': round(entry_est + (risk_dist * config.RISK_REWARD_TP1 * 2.0), 4),
            'position_size': round(position_size, 2), 'sl_percent': round(sl_percent, 2),
            'feat_adx': round(current_candle['feat_adx'], 2), 'feat_vol_ratio': round(current_candle['feat_vol_ratio'], 2),
            'feat_atr_percent': round(current_candle['feat_atr_percent'], 2), 'feat_rsi': round(current_candle['feat_rsi'], 2),
            'feat_trend_line': current_candle['feat_trend_line'], 'feat_ema_deviation': round(current_candle['feat_ema_deviation'], 2),
            'feat_rsi_momentum': round(current_candle['feat_rsi_momentum'], 2), 'feat_body_ratio': round(current_candle['feat_body_ratio'], 2),
            'feat_high_volume_session': current_candle['feat_high_volume_session']
        }
    
    elif current_candle['Close'] < last_swing_low and current_candle['Volume'] > current_candle['Volume_MA']:
        return {
            'pair': pair, 'direction': 'SHORT', 'entry_price': round(entry_est, 4),
            'stop_loss': round(entry_est + risk_dist, 4), 'tp1': round(entry_est - (risk_dist * config.RISK_REWARD_TP1), 4),
            'tp2': round(entry_est - (risk_dist * config.RISK_REWARD_TP1 * 2.0), 4),
            'position_size': round(position_size, 2), 'sl_percent': round(sl_percent, 2),
            'feat_adx': round(current_candle['feat_adx'], 2), 'feat_vol_ratio': round(current_candle['feat_vol_ratio'], 2),
            'feat_atr_percent': round(current_candle['feat_atr_percent'], 2), 'feat_rsi': round(current_candle['feat_rsi'], 2),
            'feat_trend_line': current_candle['feat_trend_line'], 'feat_ema_deviation': round(current_candle['feat_ema_deviation'], 2),
            'feat_rsi_momentum': round(current_candle['feat_rsi_momentum'], 2), 'feat_body_ratio': round(current_candle['feat_body_ratio'], 2),
            'feat_high_volume_session': current_candle['feat_high_volume_session']
        }
    return None

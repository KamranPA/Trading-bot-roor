# src/strategy.py
# نسخه اصلاح‌شده v7.9 - کالیبره شده بر اساس حروف بزرگ کندل‌ها و سازگار با متد دیتابیس

import pandas as pd
import config
from src import database

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
    
    # فیلتر اولیه قدرت روند بر اساس ADX با حروف بزرگ
    if current_candle['ADX'] < config.ADX_THRESHOLD:
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
        return None

    # استخراج مقادیر لایو تکنیکال
    entry_est = float(current_candle['Close'])
    atr_val = current_candle['ATR'] if current_candle['ATR'] > 0 else (entry_est * 0.02)
    atr_percent = float((atr_val / entry_est) * 100)
    vol_ratio = float(current_candle['feat_vol_ratio'])
    
    adx_val = float(current_candle['feat_adx'])
    rsi_val = float(current_candle['feat_rsi'])
    trend_line = float(current_candle['feat_trend_line'])
    ema_dev = float(current_candle['feat_ema_deviation'])
    rsi_mom = float(current_candle['feat_rsi_momentum'])
    body_rat = float(current_candle['feat_body_ratio'])
    high_vol_session = float(current_candle['feat_high_volume_session'])

    # شرط ورود به معامله خرید (LONG)
    if current_candle['Close'] > last_swing_high and current_candle['Volume'] > current_candle['Volume_MA']:
        sl = entry_est - (1.5 * atr_val)
        risk_dist = entry_est - sl
        tp1 = entry_est + (risk_dist * config.RISK_REWARD_TP1)
        tp2 = entry_est + (risk_dist * config.RISK_REWARD_TP1 * 2.0)
        
        database.log_scan(symbol, f"Signal LONG | Entry: {round(entry_est, 4)} | AI Processing")
        
        # دیکشنری خروجی شامل فاکتورهای پایه و تکمیلی هوش مصنوعی
        return {
            'pair': pair, 'direction': 'LONG', 'entry_price': round(entry_est, 4),
            'stop_loss': round(sl, 4), 'tp1': round(tp1, 4), 'tp2': round(tp2, 4),
            'feat_adx': round(adx_val, 2), 'feat_vol_ratio': round(vol_ratio, 2), 
            'feat_atr_percent': round(atr_percent, 2), 'feat_rsi': round(rsi_val, 2), 
            'feat_trend_line': trend_line,
            'feat_ema_deviation': round(ema_dev, 2), 'feat_rsi_momentum': round(rsi_mom, 2),
            'feat_body_ratio': round(body_rat, 2), 'feat_high_volume_session': high_vol_session
        }

    # شرط ورود به معامله فروش (SHORT)
    elif current_candle['Close'] < last_swing_low and current_candle['Volume'] > current_candle['Volume_MA']:
        sl = entry_est + (1.5 * atr_val)
        risk_dist = sl - entry_est
        tp1 = entry_est - (risk_dist * config.RISK_REWARD_TP1)
        tp2 = entry_est - (risk_dist * config.RISK_REWARD_TP1 * 2.0)
        
        database.log_scan(symbol, f"Signal SHORT | Entry: {round(entry_est, 4)} | AI Processing")
        
        return {
            'pair': pair, 'direction': 'SHORT', 'entry_price': round(entry_est, 4),
            'stop_loss': round(sl, 4), 'tp1': round(tp1, 4), 'tp2': round(tp2, 4),
            'feat_adx': round(adx_val, 2), 'feat_vol_ratio': round(vol_ratio, 2), 
            'feat_atr_percent': round(atr_percent, 2), 'feat_rsi': round(rsi_val, 2), 
            'feat_trend_line': trend_line,
            'feat_ema_deviation': round(ema_dev, 2), 'feat_rsi_momentum': round(rsi_mom, 2),
            'feat_body_ratio': round(body_rat, 2), 'feat_high_volume_session': high_vol_session
        }

    return None

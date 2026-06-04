# src/indicators.py
# ماژول محاسبات اندیکاتورهای تکنیکال (نسخه v5.6 - مجهز به سنسورهای ۳۶۰ درجه)

import pandas as pd
import config

def calculate_indicators(df):
    """محاسبه مستقل اندیکاتورهای ATR، ADX، Volume_MA، RSI و EMA 200 با بالاترین دقت"""
    if df is None or df.empty or len(df) < 25:
        return None
    
    # --- ۱. محاسبه اندیکاتور ATR ---
    high_low = df['High'] - df['Low']
    high_close_prev = (df['High'] - df['Close'].shift(1)).abs()
    low_close_prev = (df['Low'] - df['Close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=config.ATR_PERIOD).mean()
    
    # --- ۲. محاسبه اندیکاتور ADX ---
    up_move = df['High'] - df['High'].shift(1)
    down_move = df['Low'].shift(1) - df['Low']
    plus_dm = (up_move > down_move) & (up_move > 0)
    plus_dm = up_move * plus_dm
    minus_dm = (down_move > up_move) & (down_move > 0)
    minus_dm = down_move * minus_dm
    tr_smoothed = tr.rolling(window=config.ADX_PERIOD).sum()
    plus_di = 100 * (plus_dm.rolling(window=config.ADX_PERIOD).sum() / tr_smoothed)
    minus_di = 100 * (minus_dm.rolling(window=config.ADX_PERIOD).sum() / tr_smoothed)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    df['ADX'] = dx.rolling(window=config.ADX_PERIOD).mean()
    
    # --- ۳. محاسبه میانگین متحرک حجم ---
    df['Volume_MA'] = df['Volume'].rolling(window=config.VOLUME_MA_PERIOD).mean()
    
    # --- 📈 ۴. محاسبه اندیکاتور RSI (شاخص قدرت نسبی) ---
    change = df['Close'].diff()
    gain = change.mask(change < 0, 0)
    loss = -change.mask(change > 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # --- 📈 ۵. محاسبه اندیکاتور EMA 200 (خط روند ماژور) ---
    df['EMA_200'] = df['Close'].ewm(span=len(df), adjust=False).mean()
    
    # پر کردن فضاهای خالی اولیه برای جلوگیری از ارور محاسباتی در یادگیری ماشین
    df.bfill(inplace=True)
    df.ffill(inplace=True)
    
    return df

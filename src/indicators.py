# src/indicators.py
# ماژول محاسبات اندیکاتورهای تکنیکال

import pandas as pd
import pandas_ta as ta
import config  # وارد کردن تنظیمات مرکزی که در قدم قبل ساختیم

def calculate_indicators(df):
    """
    این تابع جدول قیمت‌ها (df) را می‌گیرد و ستون‌های 
    ATR، ADX و میانگین حجم را به آن اضافه می‌کند.
    """
    # در صورتی که دیتایی وجود نداشته باشد، عملیات متوقف می‌شود
    if df is None or df.empty:
        return None
    
    # ۱. محاسبه اندیکاتور ATR (برای حد ضرر داینامیک)
    # خروجی این ابزار، میزان نوسان ارز بر حسب دلار را به ما می‌دهد
    df['ATR'] = ta.atr(high=df['High'], low=df['Low'], close=df['Close'], length=config.ATR_PERIOD)
    
    # ۲. محاسبه اندیکاتور ADX (برای تشخیص وجود روند)
    # این کتابخانه چند ستون خروجی می‌دهد، ما فقط به ستون اصلی ADX نیاز داریم
    adx_df = ta.adx(high=df['High'], low=df['Low'], close=df['Close'], length=config.ADX_PERIOD)
    if adx_df is not None:
        # نام ستون اصلی در این کتابخانه معمولاً 'ADX_14' است
        df['ADX'] = adx_df[f'ADX_{config.ADX_PERIOD}']
    
    # ۳. محاسبه میانگین متحرک حجم (برای تایید قدرت شکست)
    # حجم معاملات کندل فعلی را با میانگین ۲۰ کندل قبل مقایسه خواهیم کرد
    df['Volume_MA'] = ta.sma(df['Volume'], length=config.VOLUME_MA_PERIOD)
    
    return df

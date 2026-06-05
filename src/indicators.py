# src/indicators.py
# نسخه بدون خطای v7.2 - عایق‌بندی شده در برابر خطاهای کرش زمانی و پنداس

import pandas as pd
import numpy as np
from datetime import datetime

def calculate_indicators(df):
    """📊 محاسبه دقیق اندیکاتورهای تکنیکال و فاکتورهای پیشرفته هوش مصنوعی بدون ریسک کرش"""
    if df is None or df.empty or len(df) < 200:
        print(f"⚠️ دیتای کافی برای محاسبات تکنیکال وجود ندارد.")
        return df

    try:
        # ۱. محاسبه میانگین متحرک نمایی ۲۰۰ (EMA 200)
        df['ema_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        # ۲. محاسبه شاخص قدرت نسبی (RSI 14)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-10)
        df['feat_rsi'] = 100 - (100 / (1 + rs))
        df['feat_rsi'] = df['feat_rsi'].fillna(50.0)

        # ۳. محاسبه میانگین محدوده واقعی (ATR 14) و درصد آن
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=14).mean()
        df['feat_atr_percent'] = (df['atr'] / df['Close']) * 100
        df['feat_atr_percent'] = df['feat_atr_percent'].fillna(0.0)

        # ۴. محاسبه شاخص میانگین حرکت جهت‌دار (ADX 14)
        up_move = df['High'].diff()
        down_move = df['Low'].diff()
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        tr_smooth = tr.rolling(window=14).sum()
        plus_di = 100 * (pd.Series(plus_dm).rolling(window=14).sum() / (tr_smooth + 1e-10))
        minus_di = 100 * (pd.Series(minus_dm).rolling(window=14).sum() / (tr_smooth + 1e-10))
        
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)) * 100
        df['ADX'] = dx.rolling(window=14).mean().fillna(25.0)
        df['feat_adx'] = df['ADX']

        # ۵. محاسبه نسبت حجم معاملاتی و حجم متحرک برای استراتژی
        df['Volume_MA'] = df['Volume'].rolling(window=20).mean()
        df['feat_vol_ratio'] = (df['Volume'] / (df['Volume_MA'] + 1e-10)).fillna(1.0)

        # ۶. تشخیص خط روند داینامیک
        df['feat_trend_line'] = np.where(df['Close'] > df['ema_200'], 1.0, 0.0)

        # =========================================================================
        # 🔥 بلاک هوش مصنوعی ایمن (Safe AI Features)
        # =========================================================================
        # انحراف قیمت از EMA 200
        df['feat_ema_deviation'] = ((df['Close'] - df['ema_200']) / df['ema_200']) * 100
        df['feat_ema_deviation'] = df['feat_ema_deviation'].fillna(0.0)

        # شتاب تغییرات RSI
        df['feat_rsi_momentum'] = df['feat_rsi'].diff(periods=2).fillna(0.0)

        # پرایس اکشن: نسبت اندازه بدنه کندل به کل محدوده نوسان آن
        candle_range = df['High'] - df['Low'] + 1e-10
        candle_body = (df['Close'] - df['Open']).abs()
        df['feat_body_ratio'] = (candle_body / candle_range).fillna(0.5)

        # 🛡️ اصلاح ساختاری باگ زمان: تبدیل کاملاً ایمن بدون تکیه بر متدهای ریسکی پنداس
        try:
            if 'Timestamp' in df.columns:
                # تبدیل میلی‌ثانیه‌ای یا متنی به فرمت استاندارد زمان به صورت بسیار امن
                timestamps = pd.to_datetime(df['Timestamp'], unit='ms', errors='coerce')
                # اگر فرمت متنی بود و میلی‌ثانیه‌ای نبود، مجدد تلاش کند
                if timestamps.isna().all():
                    timestamps = pd.to_datetime(df['Timestamp'], errors='coerce')
                
                df['feat_hour'] = timestamps.dt.hour.fillna(datetime.utcnow().hour).astype(float)
            else:
                df['feat_hour'] = float(datetime.utcnow().hour)
        except Exception as time_err:
            print(f"⚠️ هشدارهای زمانی نادیده گرفته شد: {time_err}")
            df['feat_hour'] = float(datetime.utcnow().hour)

        # تشخیص سشن معاملاتی پرحجم بر اساس ساعت به دست آمده
        df['feat_high_volume_session'] = np.where((df['feat_hour'] >= 12) & (df['feat_hour'] <= 20), 1.0, 0.0)

        # ستون‌های آلیاس (Alias) جهت سازگاری معکوس ۱۰۰٪ با بخش‌های قدیمی سیستم
        df['RSI'] = df['feat_rsi']
        df['EMA_200'] = df['ema_200']
        df['ATR'] = df['atr']

    except Exception as global_err:
        print(f"❌ خطای بحرانی در محاسبه اندیکاتورها رخ داد اما نادیده گرفته شد: {global_err}")
        # پر کردن ستون‌های کلیدی به صورت اضطراری برای جلوگیری از کرش کل ربات
        for col in ['ema_200', 'feat_rsi', 'atr', 'feat_atr_percent', 'ADX', 'feat_adx', 
                    'feat_vol_ratio', 'feat_trend_line', 'feat_ema_deviation', 
                    'feat_rsi_momentum', 'feat_body_ratio', 'feat_hour', 'feat_high_volume_session']:
            if col not in df.columns:
                df[col] = 0.0
        df['RSI'] = df.get('feat_rsi', 50.0)
        df['EMA_200'] = df.get('ema_200', df['Close'])
        df['ATR'] = df.get('atr', df['Close'] * 0.02)
        df['Volume_MA'] = df.get('Volume', 1.0)

    return df

# src/strategy.py
# نسخه نهایی و کاملاً هماهنگ با موتور هوش مصنوعی و دیتابیس

import os
import numpy as np
import pandas as pd
import joblib
from src import database

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "src", "models", "trading_filter_model.pkl")

def evaluate_market_and_trade(df, symbol="BTC/USDT"):
    """
    📊 بررسی وضعیت بازار، اعمال استراتژی تکنیکال، فیلترینگ با هوش مصنوعی و ثبت سیگنال
    """
    if df is None or len(df) < 2:
        print(f"⚠️ دیتای کافی برای نماد {symbol} جهت پردازش استراتژی وجود ندارد.")
        return

    # دریافت آخرین کندل بسته شده بازار
    current_candle = df.iloc[-1]
    
    # 🔍 ۱. استخراج و ایمن‌سازی مقادیر اندیکاتورها (هماهنگ با indicators.py)
    adx_val = float(current_candle['feat_adx']) if 'feat_adx' in current_candle else 25.0
    vol_ratio = float(current_candle['feat_vol_ratio']) if 'feat_vol_ratio' in current_candle else 1.0
    atr_percent = float(current_candle['feat_atr_percent']) if 'feat_atr_percent' in current_candle else 0.0
    rsi_val = float(current_candle['feat_rsi']) if 'feat_rsi' in current_candle else 50.0
    trend_line = float(current_candle['feat_trend_line']) if 'feat_trend_line' in current_candle else 0.0
    
    entry_price = float(current_candle['Close'])

    # 🛠️ ۲. منطق استراتژی تکنیکال (تحلیل روند و مومنتوم)
    # سیگنال خرید تکنیکال: روند صعودی باشد و شاخص RSI از منطقه اشباع فروش خارج یا صعودی باشد
    technical_buy_signal = (trend_line > 0) and (rsi_val > 45) and (vol_ratio > 1.1)
    
    if not technical_buy_signal:
        print(f"❄️ نماد {symbol} در این ردیف شرایط ورود تکنیکال را احراز نکرد.")
        return

    print(f"🎯 سیگنال تکنیکال برای {symbol} صادر شد. قیمت ورود: {entry_price} | ورود به فاز تایید هوش مصنوعی...")

    # 🧠 ۳. فیلترینگ پیشرفته با مدل هوش مصنوعی (Random Forest)
    ai_approved = False
    ai_confidence = 1.0  # مقدار پیش‌فرض در صورت عدم وجود مدل

    if os.path.exists(MODEL_PATH):
        try:
            # بارگذاری مدل هوش مصنوعی ذخیره شده
            model = joblib.load(MODEL_PATH)
            
            # آماده‌سازی دقیق ویژگی‌ها برای تغذیه به مدل (دقیقاً با همان ترتیب آموزش)
            features_array = np.array([[adx_val, vol_ratio, atr_percent, rsi_val, trend_line]])
            
            # محاسبه احتمال موفقیت پوزیشن (کلاس ۱ یعنی پوزیشن سودده)
            probabilities = model.predict_proba(features_array)[0]
            ai_confidence = float(probabilities[1])  # درصد احتمال سوددهی
            
            # حد آستانه صلب: اگر احتمال موفقیت بالای ۵۵٪ بود پوزیشن تایید می‌شود
            if ai_confidence >= 0.55:
                ai_approved = True
                print(f"🟢 هوش مصنوعی سیگنال را تایید کرد! درصد اطمینان مدل: {ai_confidence:.2%}")
            else:
                print(f"🔴 هوش مصنوعی سیگنال را رد کرد. درصد اطمینان ({ai_confidence:.2%}) کمتر از حد مجاز (55%) است.")
                return
        except Exception as e:
            print(f"⚠️ خطا در بارگذاری یا پیش‌بینی مدل هوش مصنوعی: {e}. سیگنال با فیلتر پیش‌فرض ارسال می‌شود.")
            ai_approved = True
    else:
        # اگر هنوز فایلی ساخته نشده (زیر ۵۰ معامله تاریخی)، پوزیشن بدون فیلتر هوش مصنوعی صادر می‌شود
        print("ℹ️ مدل هوش مصنوعی هنوز آموزش ندیده است (نیاز به دیتای تاریخی بیشتر). تایید خودکار صادر شد.")
        ai_approved = True

    # 💰 ۴. محاسبه دقیق سطوح مدیریت سرمایه (تارگت و حد ضرر بر اساس ATR)
    # اگر ATR در دسترس نبود، از ۲٪ پیش‌فرض استفاده می‌شود
    risk_factor = atr_percent if atr_percent > 0 else 0.02
    
    stop_loss = entry_price * (1.0 - risk_factor)
    take_profit = entry_price * (1.0 + (risk_factor * 2.0)) # ریسک به ریوارد ۱ به ۲

    # 💾 ۵. ساختاردهی و ثبت نهایی در دیتابیس پروژه
    signal_data = {
        'symbol': symbol,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'take_profit': take_profit,
        'feat_adx': adx_val,
        'feat_vol_ratio': vol_ratio,
        'feat_atr_percent': atr_percent,
        'feat_rsi': rsi_val,
        'feat_trend_line': trend_line,
        'ai_confidence': ai_confidence
    }

    try:
        # فراخوانی تابع ذخیره‌سازی از ماژول دیتابیس
        database.save_signal_advanced(signal_data)
        print(f"💾 سیگنال {symbol} با موفقیت در دیتابیس ثبت و ذخیره شد.")
    except Exception as e:
        print(f"❌ خطا در ثبت سیگنال در دیتابیس: {e}")

if __name__ == "__main__":
    # تست محلی صحت اجرای کدهای فایل استراتژی با دیتای فرضی
    print("🧪 در حال تست ساختار فایل استراتژی...")
    mock_data = pd.DataFrame([{
        'Close': 65000.0,
        'feat_adx': 28.5,
        'feat_vol_ratio': 1.5,
        'feat_atr_percent': 0.025,
        'feat_rsi': 55.0,
        'feat_trend_line': 1.0
    }])
    evaluate_market_and_trade(mock_data, "BTC/USDT")

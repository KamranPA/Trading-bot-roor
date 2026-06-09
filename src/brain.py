# File Path: src/brain.py
import os
import joblib  # اصلاح شد: استفاده از joblib استاندارد پایتون به جای اشتباه تایپی قبلی
import pandas as pd
import numpy as np
from config import ML_MODEL_PATH

class TradingBrain:
    def __init__(self):
        self.model = None
        self.load_model()

    def load_model(self):
        """بارگذاری مدل هوش مصنوعی از مسیر تعیین شده"""
        if os.path.exists(ML_MODEL_PATH):
            try:
                # اصلاح شد: تصحیح متد بارگذاری فایل مدل
                self.model = joblib.load(ML_MODEL_PATH)
                print("🧠 [Brain] مدل هوش مصنوعی با موفقیت بارگذاری شد.")
            except Exception as e:
                print(f"⚠️ [Brain] خطا در بارگذاری مدل هوش مصنوعی: {e}")
                self.model = None
        else:
            print("ℹ️ [Brain] مدل هوش مصنوعی یافت نشد. فیلتر ML غیرفعال است.")
            self.model = None

    def predict_signal_quality(self, atr, adx, rsi, ema_diff):
        """
        پیش‌بینی سودده بودن یا زیان‌ده بودن سیگنال بر اساس داده‌های تکنیکال
        خروجی: True (تایید سیگنال) یا False (رد سیگنال)
        """
        if self.model is None:
            # اگر مدلی آموزش داده نشده باشد، به صورت پیش‌فرض تمام سیگنال‌های پرایس‌اکشن تایید می‌شوند
            return True
            
        try:
            # ساخت دیتافریم منطبق با ویژگی‌های زمان آموزش
            features = pd.DataFrame([{
                'atr': float(atr),
                'adx': float(adx),
                'rsi': float(rsi),
                'ema_diff': float(ema_diff)
            }])
            
            prediction = self.model.predict(features)[0]
            # فرض بر این است که خروجی ۱ یعنی معامله موفق و خروجی ۰ یعنی ناموفق
            return bool(prediction == 1)
        except Exception as e:
            print(f"❌ [Brain] خطا در پیش‌بینی مدل هوش مصنوعی: {e}")
            return True

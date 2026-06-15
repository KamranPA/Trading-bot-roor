# ---------------------------------------------------------
# FILE PATH: src/brain.py (v8.8 - Ultra Safe Predictor)
# ---------------------------------------------------------
import os
import sys
import joblib
import pandas as pd
import numpy as np

# تنظیم مسیر پایه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config

class TradingBrain:
    def __init__(self):
        self.models = {}
        self._load_models()

    def _load_models(self):
        models_dir = os.path.join(BASE_DIR, "src", "models")
        if not os.path.exists(models_dir):
            return
            
        for filename in os.listdir(models_dir):
            if filename.endswith("_model.pkl"):
                symbol = filename.replace("_model.pkl", "").replace("_", "/")
                model_path = os.path.join(models_dir, filename)
                try:
                    self.models[symbol] = joblib.load(model_path)
                    print(f"🧠 مدل {symbol} با موفقیت در مغز ربات لود شد.")
                except Exception as e:
                    print(f"⚠️ خطا در لود مدل {symbol}: {e}")

    def predict_signal(self, symbol, current_features):
        """
        دریافت ویژگی‌ها (به صورت دیکشنری، سری یا دیتافریم) و پیش‌بینی امن
        """
        # اگر مدلی برای این ارز ساخته نشده است، سیگنال پیش‌فرض تایید می‌شود
        if symbol not in self.models:
            return True

        model = self.models[symbol]
        
        try:
            # ۱. یکپارچه‌سازی نوع ورودی به دیتافریم
            if isinstance(current_features, dict):
                df_features = pd.DataFrame([current_features])
            elif isinstance(current_features, pd.Series):
                df_features = pd.DataFrame([current_features.to_dict()])
            else:
                df_features = current_features.copy()

            # ۲. استخراج لیست ویژگی‌هایی که مدل در زمان آموزش یاد گرفته است
            if hasattr(model, 'feature_name_'):
                model_features = model.feature_name_
            else:
                # ویژگی‌های پشتیبان
                model_features = [
                    'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
                    'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
                    'feat_body_ratio', 'feat_high_volume_session'
                ]

            # ۳. بررسی امن ستون‌ها و پر کردن جای خالی
            for feat in model_features:
                if feat not in df_features.columns:
                    # نگاشت نام‌های قدیمی مثل atr به نام جدید
                    if feat == 'feat_atr_percent' and 'atr' in df_features.columns:
                        df_features['feat_atr_percent'] = df_features['atr']
                    else:
                        df_features[feat] = 0.0

            # ۴. مرتب‌سازی دقیق ستون‌ها مطابق آنچه LightGBM انتظار دارد
            df_features = df_features[model_features]

            # ۵. تبدیل اجباری تمام مقادیر به اعشاری (Float) برای جلوگیری از خطای TypeError و DataFrame.dtypes
            df_features = df_features.astype(float)

            # ۶. پیش‌بینی بدون کرش
            prediction = model.predict(df_features)
            
            # خروجی 1 به معنای تایید پوزیشن است
            return bool(prediction[0] == 1)

        except Exception as e:
            # چاپ ارور دقیق در ترمینال برای دیباگ بدون متوقف کردن کل ربات
            print(f"❌ خطا در پیش‌بینی {symbol}: {e}")
            # در صورت کرش کردن محاسبات، برای امنیت سرمایه، معامله رد می‌شود
            return False

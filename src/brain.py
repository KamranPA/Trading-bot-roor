# ---------------------------------------------------------
# FILE PATH: src/brain.py (نسخه کامل و اصلاح‌شده)
# ---------------------------------------------------------
import os
import joblib
import logging
import pandas as pd
import lightgbm 
import config

class TradingBrain:
    def __init__(self):
        self.models_dir = os.path.join(config.BASE_DIR, "src", "models")
        self.models = {}
        self.load_all_models()

    def load_all_models(self):
        if not os.path.exists(self.models_dir):
            logging.warning(f"⚠️ پوشه مدل‌ها یافت نشد: {self.models_dir}")
            return
            
        for file_name in os.listdir(self.models_dir):
            if file_name.endswith("_model.pkl"):
                # استخراج نام ارز: حذف _model.pkl از آخر و تبدیل _ به /
                pair = file_name.replace("_model.pkl", "").replace("_", "/")
                model_path = os.path.join(self.models_dir, file_name)
                try:
                    self.models[pair] = joblib.load(model_path)
                    logging.info(f"✅ مدل {pair} با موفقیت لود شد.")
                except Exception as e:
                    logging.error(f"خطا در لود مدل {pair}: {e}")

    def predict_signal(self, pair, current_features):
        """
        پیش‌بینی سیگنال بر اساس ویژگی‌های دریافتی
        """
        if pair not in self.models:
            return None 
            
        try:
            model = self.models[pair]
            
            # ۱. تبدیل دیکشنری ویژگی‌ها به DataFrame برای سازگاری با LightGBM
            df_features = pd.DataFrame([current_features])
            
            # ۲. اطمینان از اینکه ترتیب ستون‌ها با زمان آموزش مدل یکی است
            # (مدل‌های LightGBM ذخیره شده با joblib ویژگی feature_name_ را دارند)
            feature_names = model.feature_name_
            X_test = df_features[feature_names]
            
            # ۳. دریافت احتمال (0 تا 1)
            prediction_prob = model.predict_proba(X_test)[0][1]
            
            logging.info(f"📊 پیش‌بینی هوشمند برای {pair}: دقت {prediction_prob:.2f}")
            
            # ۴. بازگشت خروجی بر اساس آستانه 0.60
            return prediction_prob >= 0.60
                
        except Exception as e:
            # نمایش دقیق خطا برای جلوگیری از توقف سیستم
            logging.error(f"خطا در پیش‌بینی {pair}: {type(e).__name__} - {e}")
            return None

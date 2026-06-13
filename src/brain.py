# ---------------------------------------------------------
# FILE PATH: src/brain.py (Fixed for naming consistency)
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
            return
            
        for file_name in os.listdir(self.models_dir):
            # اصلاح: همخوانی با نام‌گذاری _model.pkl
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
        if pair not in self.models:
            return None 
            
        try:
            model = self.models[pair]
            
            # در مدل‌های LightGBM ذخیره شده با joblib، فیچرها معمولاً در ویژگی feature_name_ هستند
            # اما در برخی نسخه‌ها ممکن است نیاز به نام‌گذاری دستی داشته باشند
            feature_names = model.feature_name_
            
            X_test = current_features[feature_names]
            
            # دریافت احتمال (0 تا 1)
            prediction_prob = model.predict_proba(X_test)[0][1]
            
            # لاگ زدن دقت مدل برای تحلیل‌های بعدی
            logging.info(f"📊 پیش‌بینی هوشمند برای {pair}: دقت {prediction_prob:.2f}")
            
            return prediction_prob >= 0.60
                
        except Exception as e:
            logging.error(f"خطا در پیش‌بینی {pair}: {e}")
            return None

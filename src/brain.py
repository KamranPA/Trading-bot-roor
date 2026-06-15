# ---------------------------------------------------------
# FILE PATH: src/brain.py (اصلاح شده و سازگار با باندل)
# ---------------------------------------------------------
import os
import joblib
import logging
import pandas as pd
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
                pair = file_name.replace("_model.pkl", "").replace("_", "/")
                model_path = os.path.join(self.models_dir, file_name)
                try:
                    # لود کردن باندل ذخیره شده (شامل مدل و لیست ویژگی‌ها)
                    self.models[pair] = joblib.load(model_path)
                    logging.info(f"✅ مدل {pair} با موفقیت لود شد.")
                except Exception as e:
                    logging.error(f"خطا در لود مدل {pair}: {e}")

    def predict_signal(self, pair, current_features):
        if pair not in self.models:
            return None 
            
        try:
            # استخراج مدل و ویژگی‌ها از باندل لود شده
            bundle = self.models[pair]
            model = bundle['model']
            required_features = bundle['feature_names']
            
            # ۱. تبدیل دیکشنری به DataFrame
            df_features = pd.DataFrame([current_features])
            
            # ۲. تطبیق ویژگی‌ها: اگر ویژگی‌ای کم است، با صفر پر کن
            for feat in required_features:
                if feat not in df_features.columns:
                    df_features[feat] = 0.0
            
            # ۳. انتخاب ستون‌ها بر اساس نام‌های ذخیره شده در باندل
            X_test = df_features[required_features]
            
            # ۴. پیش‌بینی
            prediction_prob = model.predict_proba(X_test)[0][1]
            
            logging.info(f"📊 پیش‌بینی هوشمند برای {pair}: دقت {prediction_prob:.2f}")
            
            return prediction_prob >= 0.60
                
        except Exception as e:
            logging.error(f"خطا در پیش‌بینی {pair}: {type(e).__name__} - {e}")
            return None

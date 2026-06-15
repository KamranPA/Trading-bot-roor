# ---------------------------------------------------------
# FILE PATH: src/brain.py (نسخه نهایی و ایمن شده)
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
        """لود کردن تمام مدل‌های آموزش‌دیده از پوشه models"""
        if not os.path.exists(self.models_dir):
            logging.warning(f"⚠️ پوشه مدل‌ها یافت نشد: {self.models_dir}")
            return
            
        for file_name in os.listdir(self.models_dir):
            if file_name.endswith("_model.pkl"):
                pair = file_name.replace("_model.pkl", "").replace("_", "/")
                model_path = os.path.join(self.models_dir, file_name)
                try:
                    self.models[pair] = joblib.load(model_path)
                    logging.info(f"✅ مدل {pair} با موفقیت لود شد.")
                except Exception as e:
                    logging.error(f"خطا در لود مدل {pair}: {e}")

    def predict_signal(self, pair, current_features):
        """
        پیش‌بینی سیگنال با مدیریت خطاهای ساختاری دیتای ورودی
        """
        if pair not in self.models:
            return None 
            
        try:
            model = self.models[pair]
            
            # ۱. تبدیل دیکشنری به DataFrame
            df_features = pd.DataFrame([current_features])
            
            # ۲. تطبیق ویژگی‌های ورودی با نیازهای مدل
            # رفع مشکل KeyError: اگر مدلی ویژگی خاصی را بخواهد که در دیتا نیست، آن را با 0.0 پر می‌کند
            required_features = model.feature_name_
            for feat in required_features:
                if feat not in df_features.columns:
                    logging.warning(f"⚠️ ویژگی {feat} در دیتای ورودی نبود، مقدار 0.0 جایگزین شد.")
                    df_features[feat] = 0.0
            
            # ۳. انتخاب ستون‌ها بر اساس نیاز مدل
            X_test = df_features[required_features]
            
            # ۴. پیش‌بینی احتمال
            prediction_prob = model.predict_proba(X_test)[0][1]
            
            logging.info(f"📊 پیش‌بینی هوشمند برای {pair}: دقت {prediction_prob:.2f}")
            
            return prediction_prob >= 0.60
                
        except Exception as e:
            logging.error(f"خطا در پیش‌بینی {pair}: {type(e).__name__} - {e}")
            return None

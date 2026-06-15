# ---------------------------------------------------------
# FILE PATH: src/brain.py (نسخه نهایی ضدگلوله)
# ---------------------------------------------------------
import os
import re
import joblib
import logging
import pandas as pd
import config

# تنظیمات لاگ سیستم
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TradingBrain:
    def __init__(self):
        self.models_dir = os.path.join(config.BASE_DIR, "src", "models")
        self.models = {}
        self.load_all_models()

    def load_all_models(self):
        """لود کردن خودکار تمام مدل‌ها با هر نوع فرمت نام‌گذاری چسبیده یا جدا"""
        if not os.path.exists(self.models_dir):
            logging.warning(f"⚠️ پوشه مدل‌ها یافت نشد: {self.models_dir}")
            return
            
        for file_name in os.listdir(self.models_dir):
            if file_name.endswith(".pkl"):
                # ۱. پاکسازی نام فایل (مثال: ATOMUSDT_model.pkl -> ATOMUSDT)
                base_name = file_name.replace("_model.pkl", "").replace(".pkl", "")
                clean_name = re.sub(r'[^A-Za-z0-9]', '', base_name).upper()
                
                # ۲. استانداردسازی کلید به فرمت صرافی (ATOMUSDT -> ATOM/USDT)
                if clean_name.endswith("USDT"):
                    pair = clean_name[:-4] + "/USDT"
                else:
                    pair = clean_name
                
                model_path = os.path.join(self.models_dir, file_name)
                try:
                    self.models[pair] = joblib.load(model_path)
                    logging.info(f"🧠 مدل اختصاصی {pair} با موفقیت بارگذاری شد.")
                except Exception as e:
                    logging.error(f"❌ خطا در لود مدل {file_name}: {e}")

    def predict_signal(self, pair, current_features):
        """پیش‌بینی هوشمند سیگنال با تطبیق دقیق ستون‌های مدل"""
        # همسان‌سازی نام ارز ورودی صرافی با فرمت ذخیره‌شده (تبدیل به فرمت اسلش‌دار)
        clean_pair = re.sub(r'[^A-Za-z0-9]', '', pair).upper()
        if clean_pair.endswith("USDT"):
            search_pair = clean_pair[:-4] + "/USDT"
        else:
            search_pair = clean_pair

        if search_pair not in self.models:
            logging.warning(f"⚠️ مدلی برای جفت ارز {search_pair} یافت نشد. فیلتر هوش مصنوعی اعمال نمی‌شود.")
            return True 
            
        try:
            bundle = self.models[search_pair]
            
            # پشتیبانی از ساختارهای ذخیره‌سازی مختلف (دیکشنری باندل یا مدل خام)
            if isinstance(bundle, dict) and 'model' in bundle:
                model = bundle['model']
                required_features = bundle.get('feature_names', [])
            else:
                model = bundle
                required_features = [col for col in current_features.keys() if col.startswith('feat_')]
            
            df_features = pd.DataFrame([current_features])
            
            # تطبیق ستون‌ها برای جلوگیری از ارور عدم تطابق فیچرها در LightGBM
            if required_features:
                for feat in required_features:
                    if feat not in df_features.columns:
                        df_features[feat] = 0.0
                X_live = df_features[required_features]
            else:
                feat_cols = sorted([c for c in df_features.columns if c.startswith('feat_')])
                X_live = df_features[feat_cols]
            
            prediction_prob = model.predict_proba(X_live)[0][1]
            logging.info(f"📊 پیش‌بینی برای {search_pair}: احتمال موفقیت معامله {prediction_prob:.2f}")
            
            return prediction_prob >= 0.60
                
        except Exception as e:
            logging.error(f"❌ خطا در پیش‌بینی جفت ارز {search_pair}: {e}")
            return True

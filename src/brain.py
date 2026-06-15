# ---------------------------------------------------------
# FILE PATH: src/brain.py (سیستم لودینگ و پیش‌بینی هوشمند و خودکار LightGBM)
# ---------------------------------------------------------
import os
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
        """لود کردن خودکار تمام باندل‌های هوش مصنوعی موجود در پوشه مدل‌ها"""
        if not os.path.exists(self.models_dir):
            logging.warning(f"⚠️ پوشه مدل‌ها یافت نشد: {self.models_dir}")
            return
            
        for file_name in os.listdir(self.models_dir):
            if file_name.endswith("_model.pkl"):
                # تبدیل فرمت نام فایل به جفت ارز استاندارد (مثال: BTC_USDT -> BTC/USDT)
                pair = file_name.replace("_model.pkl", "").replace("_", "/")
                model_path = os.path.join(self.models_dir, file_name)
                try:
                    # لود کردن باندل ذخیره شده (شامل مدل لایت‌جی‌بی‌ام و لیست ویژگی‌های زمان آموزش)
                    self.models[pair] = joblib.load(model_path)
                    logging.info(f"🧠 مدل اختصاصی {pair} با موفقیت بارگذاری شد.")
                except Exception as e:
                    logging.error(f"❌ خطا در لود مدل {pair}: {e}")

    def predict_signal(self, pair, current_features):
        """
        پیش‌بینی هوشمند احتمال موفقیت شکست (Breakout) بر اساس مدل LightGBM اختصاصی هر ارز
        تطبیق خودکار ویژگی‌ها (Feature Alignment) جهت جلوگیری از ارور عدم تطابق ستون‌ها
        """
        if pair not in self.models:
            # اگر مدلی برای این ارز آموزش ندیده، سیگنال خام فیلتر نمی‌شود و صادر می‌گردد (سیستم پایدار)
            logging.warning(f"⚠️ مدلی برای جفت ارز {pair} یافت نشد. فیلتر هوش مصنوعی اعمال نمی‌شود.")
            return True 
            
        try:
            # استخراج مدل و ویژگی‌ها از باندل لود شده
            bundle = self.models[pair]
            model = bundle['model']
            required_features = bundle['feature_names']
            
            # ۱. تبدیل دیکشنری ویژگی‌های فعلی بازار به DataFrame
            df_features = pd.DataFrame([current_features])
            
            # ۲. تطبیق خودکار: اگر ویژگی جدیدی در فایل اندیکاتورها اضافه شده ولی مدل قدیمی آن را نمی‌شناسد، 
            # یا برعکس، مدل ستونی را می‌خواهد که در بازار نیست، با مقدار 0.0 پر می‌شود تا لایت‌جی‌بی‌ام کرش نکند.
            for feat in required_features:
                if feat not in df_features.columns:
                    df_features[feat] = 0.0
            
            # ۳. چیدمان دقیق و مرتب‌سازی ستون‌ها دقیقاً بر اساس ترتیبی که مدل با آن آموزش دیده است
            X_live = df_features[required_features]
            
            # ۴. محاسبه احتمال موفقیت معامله (خروجی بین 0.0 تا 1.0)
            prediction_prob = model.predict_proba(X_live)[0][1]
            
            logging.info(f"📊 پیش‌بینی هوشمند برای {pair}: احتمال موفقیت معامله {prediction_prob:.2f}")
            
            # ۵. شرط ورود: اگر حد نصاب بالای ۶۰٪ تایید را بیاورد، اجازه ورود صادر می‌شود
            return prediction_prob >= 0.60
                
        except Exception as e:
            logging.error(f"❌ خطا در پیش‌بینی جفت ارز {pair}: {type(e).__name__} - {e}")
            return True # در صورت بروز خطای سیستمی، ربات به کار خود ادامه می‌دهد تا سودها از دست نروند

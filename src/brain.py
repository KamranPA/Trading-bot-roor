# ---------------------------------------------------------
# FILE PATH: /src/brain.py
# ---------------------------------------------------------

import os
import joblib
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "src", "models", "trading_filter_model.pkl")

class TradingBrain:
    def __init__(self):
        """🧠 مغز متفکر هوش مصنوعی ۱۰‌بعدی"""
        self.model = None
        self.is_active = False
        
        if os.path.exists(MODEL_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                self.is_active = True
                print("🤖 [هوش مصنوعی]: مدل ۱۰‌بعدی بارگذاری شد.")
            except Exception as e:
                print(f"⚠️ خطای بارگذاری مدل: {e}")

    def predict(self, features_dict):
        """
        🔮 فیلتر هوشمند سیگنال
        """
        if not self.is_active or self.model is None:
            return True # حالتِ جمع‌آوری دیتا: همه سیگنال‌ها تایید می‌شوند

        try:
            # شناسایی ویژگی‌های مورد نیاز مدل به صورت داینامیک
            # این کار باعث می‌شود اگر مدل ۱۰ فاکتوره است، ۱۰ تا را بگیرد و اگر ۱۱ شد، اتوماتیک آپدیت شود
            feature_names = self.model.feature_names_in_ 
            
            # آماده‌سازی دیتافریم ورودی بر اساس نیاز مدل
            input_data = pd.DataFrame([{f: features_dict.get(f, 0.0) for f in feature_names}])
            
            # پیش‌بینی
            prediction = self.model.predict(input_data)[0]
            return bool(prediction == 1)
            
        except Exception as e:
            print(f"❌ خطای پیش‌بینی: {e}")
            return True 

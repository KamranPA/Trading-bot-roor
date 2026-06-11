# ---------------------------------------------------------
# FILE PATH: src/brain.py (v8.0 - Multi-Model Brain)
# ---------------------------------------------------------
import os
import joblib
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TradingBrain:
    def __init__(self):
        """🧠 مغز متفکر هوش مصنوعی با قابلیت مسیریابی پویا مابین مدل‌های اختصاصی ارزها"""
        self.cached_models = {}

    def _get_model_for_symbol(self, symbol):
        """لود کردن یا واکشی از کش برای مدل اختصاصی هر ارز"""
        safe_symbol_name = symbol.replace('/', '_')
        model_path = os.path.join(BASE_DIR, "src", "models", f"{safe_symbol_name}_model.pkl")
        
        # اگر قبلاً لود شده، از کش استفاده کن
        if symbol in self.cached_models:
            return self.cached_models[symbol]
            
        if os.path.exists(model_path):
            try:
                model = joblib.load(model_path)
                self.cached_models[symbol] = model
                return model
            except Exception as e:
                print(f"⚠️ خطای بارگذاری مدل اختصاصی {symbol}: {e}")
        return None

    def predict(self, symbol, features_dict):
        """🔮 پیش‌بینی و فیلتر هوشمند سیگنال با مدل اختصاصی همان جفت‌ارز"""
        model = self._get_model_for_symbol(symbol)
        
        if model is None:
            # اگر هنوز مدلی برای این ارز تربیت نشده، سیگنال را مسدود نکن تا دیتا جمع شود
            return True 

        try:
            feature_names = model.feature_names_in_ 
            input_data = pd.DataFrame([{f: features_dict.get(f, 0.0) for f in feature_names}])
            
            prediction = model.predict(input_data)[0]
            return bool(prediction == 1)
            
        except Exception as e:
            print(f"❌ خطای پیش‌بینی هوش مصنوعی برای {symbol}: {e}")
            return True

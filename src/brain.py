# File Path: /src/brain.py
import os
import joblib  # اصلاح شد
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

MODEL_PATH = "ml_models/rf_trading_model.pkl"

class TradingBrain:
    def __init__(self):
        self.model = None
        self.feature_order = ['atr', 'adx', 'rsi', 'ema_diff']
        self.load_model()

    def load_model(self):
        """بارگذاری مدل هوش مصنوعی در صورت وجود"""
        if os.path.exists(MODEL_PATH):
            try:
                with open(MODEL_PATH, 'rb') as f:
                    self.model = joblib.load(f)  # اصلاح شد
                print("🧠 [Brain] مدل هوش مصنوعی با موفقیت بارگذاری شد.")
            except Exception as e:
                print(f"⚠️ [Brain] خطا در بارگذاری مدل هوش مصنوعی: {e}")
                self.model = None
        else:
            print("ℹ️ [Brain] فیلتر هوش مصنوعی فعال نیست (مدل یافت نشد). تایید خودکار اعمال می‌شود.")

    def approve_signal(self, indicators_dict):
        """بررسی سیگنال صادر شده توسط مدل هوش مصنوعی"""
        if self.model is None:
            return True  
            
        try:
            input_data = {
                'atr': indicators_dict.get('ATR', 0.0),
                'adx': indicators_dict.get('ADX', 0.0),
                'rsi': indicators_dict.get('RSI', 0.0),
                'ema_diff': indicators_dict.get('EMA_diff', 0.0)
            }
            
            df_features = pd.DataFrame([input_data], columns=self.feature_order)
            prediction = self.model.predict(df_features)[0]
            return bool(prediction == 1)
        except Exception as e:
            print(f"❌ [Brain] خطا در پردازش فیلتر هوش مصنوعی: {e}")
            return True

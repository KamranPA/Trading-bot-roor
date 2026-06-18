# ---------------------------------------------------------
# FILE PATH: src/brain.py (v9.0 - Probability Predictor Engine)
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

    def _prepare_features(self, current_features, model):
        """متد کمکی برای پاکسازی و آماده‌سازی امن ورودی‌ها"""
        if isinstance(current_features, dict):
            df_features = pd.DataFrame([current_features])
        elif isinstance(current_features, pd.Series):
            df_features = pd.DataFrame([current_features.to_dict()])
        else:
            df_features = current_features.copy()

        if hasattr(model, 'feature_name_'):
            model_features = model.feature_name_
        else:
            model_features = [
                'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
                'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
                'feat_body_ratio', 'feat_high_volume_session'
            ]

        for feat in model_features:
            if feat not in df_features.columns:
                if feat == 'feat_atr_percent' and 'atr' in df_features.columns:
                    df_features['feat_atr_percent'] = df_features['atr']
                else:
                    df_features[feat] = 0.0

        df_features = df_features[model_features].fillna(0.0)
        df_features = df_features.astype(np.float32)
        return df_features

    def predict_signal(self, symbol, current_features):
        """متد قدیمی باینری (برای سازگاری با کدهای احتمالی قدیمی)"""
        if symbol not in self.models:
            return True

        try:
            model = self.models[symbol]
            df_features = self._prepare_features(current_features, model)
            
            if df_features.empty or df_features.shape[1] == 0:
                print(f"⚠️ هشدار: داده ورودی برای {symbol} خالی است.")
                return False

            prediction = model.predict(df_features)
            return bool(prediction[0] == 1)
        except Exception as e:
            print(f"❌ خطای بحرانی در پیش‌بینی {symbol}: {e}")
            return False

    def predict_probability(self, symbol, current_features):
        """
        دریافت ویژگی‌ها و پیش‌بینی درصد اطمینان مدل (Probability) 
        برای اتصال به سیستم استراتژی امتیازدهی
        """
        # اگر مدلی نیست، درصد خنثی ۵۰٪ برگردان تا استراتژی با اندیکاتورها تصمیم بگیرد
        if symbol not in self.models:
            return 50.0

        try:
            model = self.models[symbol]
            df_features = self._prepare_features(current_features, model)
            
            if df_features.empty or df_features.shape[1] == 0:
                return 0.0

            # استخراج احتمال کلاس ۱ (تایید سیگنال)
            probas = model.predict_proba(df_features)
            probability_score = float(probas[0][1]) * 100.0
            
            return probability_score
            
        except Exception as e:
            print(f"❌ خطای بحرانی در پیش‌بینی احتمال {symbol}: {e}")
            return 0.0

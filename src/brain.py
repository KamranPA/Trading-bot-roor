# ---------------------------------------------------------
# FILE PATH: src/brain.py (v9.0 - Smart No-Model Handling)
# تغییرات نسبت به v8.9:
#   - اضافه شدن has_model() برای تشخیص وجود مدل آموزش‌دیده
#   - NO_MODEL_PROBABILITY حذف شد — backtester مستقیم رفتار را مدیریت می‌کند
# ---------------------------------------------------------
import os
import sys
import joblib
import pandas as pd
import numpy as np

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

    def has_model(self, symbol: str) -> bool:
        """آیا مدل آموزش‌دیده برای این ارز وجود دارد؟"""
        return symbol in self.models

    def _prepare_features(self, model, current_features):
        """
        ورودی فیچرها را به DataFrame تک‌ردیفی با ستون‌های موردانتظار مدل تبدیل می‌کند.
        """
        if isinstance(current_features, dict):
            df_features = pd.DataFrame([current_features])
        elif isinstance(current_features, pd.Series):
            df_features = pd.DataFrame([current_features.to_dict()])
        else:
            df_features = current_features.copy()

        if hasattr(model, 'feature_name_'):
            model_features = list(model.feature_name_)
        else:
            model_features = list(config.AI_FEATURES)

        for feat in model_features:
            if feat not in df_features.columns:
                if feat == 'feat_atr_percent' and 'atr' in df_features.columns:
                    df_features['feat_atr_percent'] = df_features['atr']
                else:
                    df_features[feat] = 0.0

        df_features = df_features[model_features].fillna(0.0).astype(np.float32)
        return df_features

    def predict_probability(self, symbol, current_features):
        """
        احتمال موفقیت سیگنال (۰ تا ۱).
        اگر مدلی وجود نداشته باشد، None برمی‌گرداند تا backtester خودش تصمیم بگیرد.
        در صورت خطا، ۰.۰ (رد سیگنال) برمی‌گرداند.
        """
        if symbol not in self.models:
            return None  # backtester تصمیم می‌گیرد

        model = self.models[symbol]
        try:
            df_features = self._prepare_features(model, current_features)
            if df_features.empty or df_features.shape[1] == 0:
                print(f"⚠️ هشدار: داده ورودی برای {symbol} خالی است.")
                return 0.0

            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(df_features)
                return float(proba[0][1])

            prediction = model.predict(df_features)
            return float(prediction[0])

        except Exception as e:
            print(f"❌ خطای بحرانی در predict_probability {symbol}: {e}")
            return 0.0

    def predict_signal(self, symbol, current_features):
        """تصمیم باینری. اگر مدلی نباشد True (اجازه عبور) برمی‌گردد."""
        if symbol not in self.models:
            return True

        model = self.models[symbol]
        try:
            df_features = self._prepare_features(model, current_features)
            if df_features.empty or df_features.shape[1] == 0:
                return False
            prediction = model.predict(df_features)
            return bool(prediction[0] == 1)
        except Exception as e:
            print(f"❌ خطای بحرانی در پیش‌بینی {symbol}: {e}")
            return False

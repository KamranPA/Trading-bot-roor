# ---------------------------------------------------------
# FILE PATH: src/brain.py (v9.1 - Fix model key alignment)
# تغییرات نسبت به v9.0:
#   ✅ _load_models: نام فایل به BTC/USDT تبدیل می‌شود
#      BTC_USDT_model.pkl → key='BTC/USDT' (سازگار با _to_brain_symbol)
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
            if not filename.endswith("_model.pkl"):
                continue

            # ✅ FIX: BTC_USDT_model.pkl → 'BTC/USDT'
            # این دقیقاً همان کلیدی است که _to_brain_symbol در
            # strategy.py و backtester.py تولید می‌کند.
            symbol = filename.replace("_model.pkl", "").replace("_", "/")

            model_path = os.path.join(models_dir, filename)
            try:
                self.models[symbol] = joblib.load(model_path)
                print(f"🧠 مدل '{symbol}' لود شد ← {filename}")
            except Exception as e:
                print(f"⚠️ خطا در لود مدل {filename}: {e}")

    def has_model(self, symbol: str) -> bool:
        """آیا مدل آموزش‌دیده برای این ارز وجود دارد؟"""
        return symbol in self.models

    def _prepare_features(self, model, current_features):
        """ورودی فیچرها را به DataFrame تک‌ردیفی تبدیل می‌کند."""
        if isinstance(current_features, dict):
            df_features = pd.DataFrame([current_features])
        elif isinstance(current_features, pd.Series):
            df_features = pd.DataFrame([current_features.to_dict()])
        else:
            df_features = current_features.copy()

        # فیچرهای موردانتظار مدل
        if hasattr(model, 'feature_name_'):
            model_features = list(model.feature_name_)
        else:
            model_features = list(config.AI_FEATURES)

        # اضافه کردن فیچرهای گمشده با مقدار 0
        for feat in model_features:
            if feat not in df_features.columns:
                df_features[feat] = 0.0

        df_features = df_features[model_features].fillna(0.0).astype(np.float32)
        return df_features

    def predict_probability(self, symbol: str, current_features) -> float | None:
        """
        احتمال موفقیت سیگنال (۰ تا ۱).
        اگر مدلی وجود نداشته باشد، None برمی‌گرداند.
        """
        if symbol not in self.models:
            return None

        model = self.models[symbol]
        try:
            df_features = self._prepare_features(model, current_features)
            if df_features.empty or df_features.shape[1] == 0:
                print(f"⚠️ داده ورودی برای {symbol} خالی است.")
                return 0.0

            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(df_features)
                return float(proba[0][1])

            prediction = model.predict(df_features)
            return float(prediction[0])

        except Exception as e:
            print(f"❌ خطا در predict_probability {symbol}: {e}")
            return 0.0

    def predict_signal(self, symbol: str, current_features) -> bool:
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
            print(f"❌ خطا در predict_signal {symbol}: {e}")
            return False

# src/brain.py
import os
import joblib
import pandas as pd
import config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "src", "models", "trading_filter_model.pkl")

class TradingBrain:
    def __init__(self):
        self.model = None
        self.is_active = False
        if os.path.exists(MODEL_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                self.is_active = True
            except Exception as e:
                print(f"⚠️ خطا در بارگذاری مدل: {e}")

    def predict(self, features_dict):
        if not self.is_active or self.model is None:
            return True 
        try:
            features_ordered = [
                'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line',
                'feat_ema_deviation', 'feat_rsi_momentum', 'feat_body_ratio', 'feat_high_volume_session'
            ]
            input_data = pd.DataFrame([{f: features_dict.get(f, 0.0) for f in features_ordered}])
            prediction = self.model.predict(input_data)[0]
            return bool(prediction == 1)
        except Exception:
            return True

# 🟢 ایجاد یک نمونه سراسری (Global Instance) برای استفاده در سایر فایل‌ها
brain_instance = TradingBrain()

def check_ai_permission(signal_data):
    """
    تابع واسط (Wrapper) که main.py به آن نیاز دارد تا خطا ندهد.
    """
    is_allowed = brain_instance.predict(signal_data)
    reason = "AI Approved" if is_allowed else "AI Blocked"
    return is_allowed, reason

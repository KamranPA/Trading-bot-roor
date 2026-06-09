# File Path: src/config.py
import os
import json

# مسیرهای اصلی پروژه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trading_bot.db")
ML_MODEL_PATH = os.path.join(BASE_DIR, "ml_models", "rf_trading_model.pkl")
PARAMS_JSON_PATH = os.path.join(BASE_DIR, "data", "best_params.json")

# پارامترهای پیش‌فرض استراتژی معاملاتی (اگر فایل بهینه‌ساز هنوز ساخته نشده باشد)
DEFAULT_PARAMS = {
    "atr_window": 14,
    "rsi_window": 14,
    "adx_window": 14,
    "adx_threshold": 25.0,
    "tp1_multiplier": 1.5,
    "tp2_multiplier": 3.0,
    "sl_multiplier": 1.5,
    "risk_percent": 0.01  # ۱ درصد ریسک در هر معامله
}

def load_current_params():
    """بارگذاری آخرین پارامترهای بهینه‌سازی شده توسط الگوریتم ارزیابی"""
    if os.path.exists(PARAMS_JSON_PATH):
        try:
            with open(PARAMS_JSON_PATH, 'r') as f:
                optimized_params = json.load(f)
                print("⚙️ [Config] پارامترهای بهینه‌سازی شده لود شدند.")
                return {**DEFAULT_PARAMS, **optimized_params}
        except Exception as e:
            print(f"⚠️ [Config] خطا در لود پارامترهای بهینه، استفاده از مقادیر پیش‌فرض: {e}")
    return DEFAULT_PARAMS

# لود و در دسترس قرار دادن پارامترها برای سایر ماژول‌ها
CURRENT_PARAMS = load_current_params()

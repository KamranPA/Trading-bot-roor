# ---------------------------------------------------------
# FILE NAME: config.py
# ---------------------------------------------------------
import os
import json

# --- ۱. مسیرهای پایه ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")
PARAMS_FILE = os.path.join(BASE_DIR, "best_params.json")

# --- ۲. تابع بارگذاری پارامترهای هوشمند ---
def load_params():
    default_params = {
        "adx_threshold": 25.0,
        "tp_ratio": 1.5,
        "sl_ratio": 1.0,
        "volume_confirmation_ratio": 1.2
    }
    if os.path.exists(PARAMS_FILE):
        try:
            with open(PARAMS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ خطا در خواندن پارامترها، استفاده از پیش‌فرض: {e}")
            return default_params
    return default_params

# بارگذاری مقادیر
_params = load_params()

# --- ۳. متغیرهای تنظیمات ---
WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "LINK/USDT", 
    "AVAX/USDT", "DOGE/USDT", "ADA/USDT", "MATIC/USDT", "DOT/USDT",
    "ARB/USDT", "OP/USDT", "ATOM/USDT", "NEAR/USDT", "FTM/USDT"
]

CANDLES_LIMIT = 500
TIMEFRAME = "4h"
COINEX_API_URL = "https://api.coinex.com/v2"

# تنظیمات استراتژی (متصل به Optimizer)
ADX_THRESHOLD = _params.get("adx_threshold", 25.0)
VOLUME_CONFIRMATION_RATIO = _params.get("volume_confirmation_ratio", 1.2)
RISK_REWARD_TP1 = _params.get("tp_ratio", 1.5)
SWING_WINDOW = 5
MAX_OPEN_POSITIONS = 15

# مدیریت سرمایه
TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 0.1

# اطلاعات حساس
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

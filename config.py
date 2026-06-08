# ---------------------------------------------------------
# FILE NAME: config.py
# ---------------------------------------------------------
import os
import json

# --- ۱. تنظیم مسیرهای پایه ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_NAME = os.path.join(DATA_DIR, "trading_bot.db")
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
        except Exception:
            return default_params
    return default_params

_params = load_params()

# --- ۳. متغیرهای تنظیمات ---
# نمادها طبق استاندارد کوینکس (بدون اسلش)
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT", "LINKUSDT", 
    "AVAXUSDT", "DOGEUSDT", "ADAUSDT", "DOTUSDT",
    "ARBUSDT", "OPUSDT", "ATOMUSDT", "NEARUSDT"
]

CANDLES_LIMIT = 500
TIMEFRAME = "4h"
COINEX_API_URL = "https://api.coinex.com/v2"

# تنظیمات استراتژی
ADX_THRESHOLD = _params.get("adx_threshold", 25.0)
VOLUME_CONFIRMATION_RATIO = _params.get("volume_confirmation_ratio", 1.2)
RISK_REWARD_TP1 = _params.get("tp_ratio", 1.5)
SWING_WINDOW = 5
MAX_OPEN_POSITIONS = 15

# مدیریت سرمایه
TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 0.1

# اطلاعات حساس با مقدار پیش‌فرض خالی برای جلوگیری از خطای Runtime
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# File Path: /config.py
import os
import json

# 🪙 لیست واچ‌لیست
WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "LINK/USDT", 
    "AVAX/USDT", "DOGE/USDT", "ADA/USDT", "POL/USDT", "DOT/USDT",
    "ARB/USDT", "OP/USDT", "ATOM/USDT", "NEAR/USDT", "TON/USDT"
]

CANDLES_LIMIT = 500
TIMEFRAME = "4h"
COINEX_API_URL = "https://api.coinex.com/v2"

SWING_WINDOW = 5                 
MAX_OPEN_POSITIONS = 15          
VOLUME_CONFIRMATION_RATIO = 1.2  

TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 0.1               
RISK_REWARD_TP1 = 1.5            
RISK_REWARD_TP2 = 2.5            

# مدیریت مسیرها بر اساس ریشه
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")
PARAMS_JSON_PATH = os.path.join(BASE_DIR, "best_params.json")

# مقدار پیش‌فرض حد آستانه ADX
ADX_THRESHOLD = 25.0

# بارگذاری داینامیک پارامترهای بهینه‌سازی شده (اگر وجود داشته باشند)
if os.path.exists(PARAMS_JSON_PATH):
    try:
        with open(PARAMS_JSON_PATH, 'r') as f:
            optimized_params = json.load(f)
            # اگر پارامتر adx_threshold در فایل بهینه‌ساز بود، آن را جایگزین کن
            if 'adx_threshold' in optimized_params:
                ADX_THRESHOLD = float(optimized_params['adx_threshold'])
                print(f"⚙️ [Config] پارامتر ADX بهینه‌سازی شده لود شد: {ADX_THRESHOLD}")
    except Exception as e:
        print(f"⚠️ [Config] خطا در لود فایل best_params.json: {e}")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

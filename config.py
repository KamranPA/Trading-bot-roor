# config.py
import os

WATCHLIST = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "SUI/USDT",
    "LINK/USDT",
    "AVAX/USDT"
]

CANDLES_LIMIT = 300
TIMEFRAME = "4h"  # 🟢 اضافه شد جهت رفع باگ کرش coinex_client
COINEX_API_URL = "https://api.coinex.com/v2"
TELEGRAM_LOCK_HOURS = 8
ADX_THRESHOLD = 25
VOLUME_MA_PERIOD = 20
SWING_WINDOW = 7
RISK_REWARD_TP1 = 1.0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

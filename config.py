# ---------------------------------------------------------
# FILE PATH: /config.py
# ---------------------------------------------------------
import os

# 🪙 لیست واچ‌لیست (MATIC و FTM با POL و TON جایگزین شدند)
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
ADX_THRESHOLD = 25               
VOLUME_CONFIRMATION_RATIO = 1.2  

TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 0.1               
RISK_REWARD_TP1 = 1.5            
RISK_REWARD_TP2 = 2.5            

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

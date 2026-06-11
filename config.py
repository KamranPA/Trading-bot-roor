# ---------------------------------------------------------
# FILE PATH: config.py (اصلاح شده برای تفکیک لایو و بکتست)
# ---------------------------------------------------------
import os

# تعیین مسیر پایه پروژه (Root Directory)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# دیتابیس اصلی و لایو (بدون تغییر نام برای حفظ پایداری ربات اصلی)
DB_NAME = "trading_bot.db"

# دیتابیس مجزا و اختصاصی برای بکتست و آموزش هوش مصنوعی
DB_NAME_BACKTEST = "trading_bot_backtest.db"


# تنظیمات فچ دیتای صرافی
TIMEFRAME = "4h"        
CANDLES_LIMIT = 500    

# تنظیمات معاملاتی و ریسک
MAX_OPEN_POSITIONS = 3
ADX_THRESHOLD = 20.0
SWING_WINDOW = 5
TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 1.0

# لیست کامل ارزهای تحت نظر
WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "POL/USDT", 
    "ADA/USDT", "DOT/USDT", "LINK/USDT", "UNI/USDT", 
    "AVAX/USDT", "XRP/USDT", "LTC/USDT", "BCH/USDT", 
    "ATOM/USDT", "NEAR/USDT"
]

# تنظیمات تلگرام (از متغیرهای محیطی خوانده می‌شود)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ---------------------------------------------------------
# FILE PATH: config.py (اصلاح شده و هماهنگ با تمام ماژول‌ها)
# ---------------------------------------------------------
import os

# تعیین مسیر پایه پروژه (Root Directory)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# دیتابیس اصلی و لایو (تبدیل به مسیر مطلق برای پایداری در گیت‌هاب اکشنز)
DB_NAME = "trading_bot.db"
DB_PATH_LIVE = os.path.join(BASE_DIR, "data", DB_NAME)

# دیتابیس مجزا و اختصاصی برای بکتست و آموزش هوش مصنوعی (مسیر مطلق)
DB_NAME_BACKTEST = "trading_bot_backtest.db"
DB_PATH_BACKTEST = os.path.join(BASE_DIR, "data", DB_NAME_BACKTEST)


# تنظیمات فچ دیتای صرافی
TIMEFRAME = "4h"        
CANDLES_LIMIT = 500    

# تنظیمات معاملاتی و ریسک
MAX_OPEN_POSITIONS = 3
ADX_THRESHOLD = 15.0
SWING_WINDOW = 3
TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 1.0

# لیست کامل ارزهای تحت نظر
WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "POL/USDT", "DOT/USDT", "LINK/USDT", 
    "AVAX/USDT", "XRP/USDT", "LTC/USDT", "BCH/USDT", 
    "ATOM/USDT"
]

# تنظیمات تلگرام (از متغیرهای محیطی خوانده می‌شود)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

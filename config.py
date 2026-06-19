# ---------------------------------------------------------
# FILE PATH: config.py (v9.1 - Cloud Aligned)
# ---------------------------------------------------------
import os

# تعیین مسیر پایه پروژه (Root Directory)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 🛠️ توجه: مسیرهای دیتابیس محلی (SQLite) غیرفعال شدند چون ربات اکنون از DATABASE_URL (PostgreSQL) استفاده می‌کند.
# DB_NAME, DB_PATH_LIVE و DB_PATH_BACKTEST صرفاً جهت حفظ ساختار باقی مانده‌اند.
DB_NAME = "trading_bot.db"
DB_PATH_LIVE = os.path.join(BASE_DIR, "data", DB_NAME)
DB_NAME_BACKTEST = "trading_bot_backtest.db"
DB_PATH_BACKTEST = os.path.join(BASE_DIR, "data", DB_NAME_BACKTEST)

# تنظیمات فچ دیتای صرافی
TIMEFRAME = "4h"        
CANDLES_LIMIT = 500    

# تنظیمات معاملاتی پایه و مدیریت ریسک
MAX_OPEN_POSITIONS = 3
ADX_THRESHOLD = 15.0   
SWING_WINDOW = 3       
TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 1.0

# نسبت‌های پیش‌فرض مدیریت پوزیشن
TP_RATIO = 1.5
SL_RATIO = 1.0
RISK_MULTIPLIER = 1.0

# وزن‌های سیستم امتیازدهی استراتژی
WEIGHT_RSI = 30
WEIGHT_ADX = 25
WEIGHT_EMA = 25
WEIGHT_AI = 20

# حداقل امتیاز کل (Total Score) مجاز برای صادر شدن سیگنال ورود لایو
MIN_REQUIRED_SCORE = 60

# لیست کامل ارزهای تحت نظر
WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "POL/USDT", "DOT/USDT", "LINK/USDT", 
    "AVAX/USDT", "XRP/USDT", "LTC/USDT", "BCH/USDT", 
    "ATOM/USDT"
]

# تنظیمات تلگرام (از متغیرهای محیطی خوانده می‌شود)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

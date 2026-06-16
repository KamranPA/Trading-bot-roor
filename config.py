# ---------------------------------------------------------
# FILE PATH: config.py (v9.0 - Fully Aligned with Scoring & Pipeline)
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

# تنظیمات معاملاتی پایه و مدیریت ریسک
MAX_OPEN_POSITIONS = 3
ADX_THRESHOLD = 15.0   # مقدار پیش‌فرض که توسط اپتیمایزر بازنویسی می‌شود
SWING_WINDOW = 3       # مقدار پیش‌فرض که توسط اپتیمایزر بازنویسی می‌شود
TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 1.0

# 🛠️ اضافه شده: نسبت‌های پیش‌فرض مدیریت پوزیشن برای هماهنگی کامل با اپتیمایزر و استراتژی
TP_RATIO = 1.5
SL_RATIO = 1.0
RISK_MULTIPLIER = 1.0

# 🧠 اضافه شده: وزن‌های سیستم امتیازدهی استراتژی جدید (بین ۰ تا ۱۰۰)
# این مقادیر تعیین می‌کنند که هر بخش چقدر در فیلتر نهایی پوزیشن‌ها سهم دارد
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

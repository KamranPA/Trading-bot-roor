# ---------------------------------------------------------
# FILE PATH: config.py
# ---------------------------------------------------------
import os

# تعیین مسیر پایه پروژه (Root Directory)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# دیتابیس در ریشه پروژه قرار می‌گیرد تا GitHub Actions بتواند آن را به عنوان Artifact ذخیره کند
DB_NAME = os.path.join(BASE_DIR, "trading_bot.db")

# تنظیمات معاملاتی
MAX_OPEN_POSITIONS = 3
ADX_THRESHOLD = 20.0
SWING_WINDOW = 5
TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 1.0

# لیست ارزهای تحت نظر (اصلاح شده)
WATCHLIST = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "POL/USDT"]

# تنظیمات تلگرام (از متغیرهای محیطی خوانده می‌شود)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

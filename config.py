# ---------------------------------------------------------
# FILE PATH: config.py (اصلاح شده و هماهنگ با تمام ماژول‌ها)
# ---------------------------------------------------------
import os

# --- تنظیمات عمومی ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
# این خط را به config.py اضافه کنید
DB_NAME = "trading_bot.db"
DB_PATH_LIVE = os.path.join(DATA_DIR, "trading_bot.db")
DB_PATH_BACKTEST = os.path.join(DATA_DIR, "trading_bot_backtest.db")

# --- تنظیمات تلگرام ---
# برای غیرفعال کردن ارسال پیام، این مقدار را False کنید
SEND_TELEGRAM_ALERTS = False 

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- لیست ارزهای تحت نظر ---
WATCHLIST = ["BTC-USD", "ETH-USD", "MATIC-USD", "SOL-USD"]

# --- تنظیمات مدیریت سرمایه ---
CAPITAL = 1000.0        # سرمایه فرضی
RISK_PER_TRADE = 0.01   # ریسک ۱ درصد
MAX_OPEN_POSITIONS = 3  # حداکثر پوزیشن‌های باز همزمان

# --- تنظیمات استراتژی ---
LOOKBACK_PERIOD = 5     # پنجره زمانی برای تشخیص Swing High/Low
ADX_THRESHOLD = 20      # آستانه قدرت روند
RSI_PERIOD = 14

# --- تنظیمات مسیر مدل‌ها ---
MODEL_DIR = os.path.join(BASE_DIR, "src", "models")

# ساخت دایرکتوری‌ها در صورت عدم وجود
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR)

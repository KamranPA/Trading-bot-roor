# ---------------------------------------------------------
# FILE NAME: config.py
# FILE PATH: /config.py
# ---------------------------------------------------------
import os

# 🪙 لیست واچ‌لیست بهینه‌شده (حذف نمادهای نامعتبر کوین‌اکس مانند MATIC و FTM برای رفع خطا)
WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "LINK/USDT", 
    "AVAX/USDT", "DOGE/USDT", "ADA/USDT", "POL/USDT", "DOT/USDT",
    "ARB/USDT", "OP/USDT", "ATOM/USDT", "NEAR/USDT", "XRP/USDT"
]

# 📊 تنظیمات داده و تایم‌فریم
CANDLES_LIMIT = 500
TIMEFRAME = "4h"
COINEX_API_URL = "https://api.coinex.com/v2"

# 🚀 تنظیمات استراتژی شکست سطوح (Breakout)
SWING_WINDOW = 5                 # تعداد کندل‌های لازم برای تشخیص قله و دره (Swing)
MAX_OPEN_POSITIONS = 15          # حداکثر تعداد پوزیشن‌های باز همزمان
ADX_THRESHOLD = 25               # حداقل قدرت روند برای ورود به معامله
VOLUME_CONFIRMATION_RATIO = 1.2  # ضریب تایید حجم معاملاتی

# 💰 مدیریت ریسک و سرمایه
TOTAL_CAPITAL = 1000.0           # کل سرمایه فرضی ربات به دلار
RISK_PERCENT = 0.1               # درصد ریسک در هر معامله
RISK_REWARD_TP1 = 1.5            # تارگت اول (ریسک به ریوارد ۱.۵) برای خروج پله‌ای و ریسک‌فری
RISK_REWARD_TP2 = 2.5            # تارگت دوم (ریسک به ریوارد ۲.۵) برای خروج کامل با سود بیشتر

# 🗄️ مسیرهای دیتابیس و تنظیمات ساختاری
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

# 🔌 اطلاعات حساس (از طریق Environment Variables در گیت‌هاب Actions خوانده می‌شود)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# 🌐 تنظیمات پروکسی اختیاری (در صورت نیاز به تست روی سیستم شخصی)
PROXY = None  # نمونه: "http://127.0.0.1:7890" (روی گیت‌هاب نیازی به پروکسی نیست)

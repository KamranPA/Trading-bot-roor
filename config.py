# ---------------------------------------------------------
# FILE PATH: /config.py
# ---------------------------------------------------------
import os

# 🪙 لیست گسترش‌یافته جهت تولید سیگنال بیشتر بدون کاهش کیفیت تکنیکال
WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "LINK/USDT", 
    "AVAX/USDT", "DOGE/USDT", "ADA/USDT", "MATIC/USDT", "DOT/USDT",
    "ARB/USDT", "OP/USDT", "ATOM/USDT", "NEAR/USDT", "FTM/USDT"
]

# 📊 تنظیمات داده (۵۰۰ کندل برای محاسبات دقیق‌ترِ میانگین حجم و RSI)
CANDLES_LIMIT = 500
TIMEFRAME = "4h"
COINEX_API_URL = "https://api.coinex.com/v2"

# 🚀 تنظیمات جمع‌آوری سریع دیتا (بدون کاهشِ استانداردهای روند)
MAX_OPEN_POSITIONS = 15          # افزایش برای ثبت همزمان معاملات بیشتر
ADX_THRESHOLD = 25               # بازگشت به ۲۵ جهت حفظ کیفیتِ روند و فیلتر بازارهای رنج
VOLUME_CONFIRMATION_RATIO = 1.2  # فیلتر ۱۰ام: حجم فعلی باید ۱.۲ برابر میانگین باشد

# مدیریت ریسک محافظه‌کارانه برای دوره آموزش هوش مصنوعی
TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 0.1               # ریسک ۰.۱٪ (فقط برای جمع‌آوری دیتا)

# 🗄️ مسیرهای دیتابیس
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

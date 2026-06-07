# config.py
import os

# لیست ارزها (افزایش تعداد جهت تولید سیگنال بیشتر در واحد زمان)
WATCHLIST = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "LINK/USDT", "AVAX/USDT", "DOGE/USDT", "ADA/USDT"]

# تنظیمات داده
CANDLES_LIMIT = 500 # افزایش برای دقت بیشتر در محاسبات
TIMEFRAME = "4h"

# 🚀 بهینه‌سازی برای جمع‌آوری سریع دیتا
MAX_OPEN_POSITIONS = 10  # افزایش شدید محدودیت برای ثبت معاملات بیشتر در دیتابیس
ADX_THRESHOLD = 15      # کاهش آستانه برای دریافت سیگنال‌های بیشتر (حتی روندهای ضعیف‌تر)

# مدیریت ریسک (بسیار محافظه‌کارانه برای دوره آموزش)
TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 0.1      # کاهش ریسک به ۰.۱٪ جهت جلوگیری از ضرر در حین آموزش مدل

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

# config.py
# نسخه نهایی v7.1 - اضافه شدن لایه تنظیمات مدیریت سرمایه و ریسک پویا

import os

# 🪙 لیست ارزهای تحت نظر ربات
WATCHLIST = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "SUI/USDT",
    "LINK/USDT",
    "AVAX/USDT"
]

# 📊 تنظیمات دریافت داده و تایم‌فریم
CANDLES_LIMIT = 300
TIMEFRAME = "4h"
COINEX_API_URL = "https://api.coinex.com/v2"

# 🛡️ محدودیت‌ها و فیلترهای زمانی
TELEGRAM_LOCK_HOURS = 8
MAX_OPEN_POSITIONS = 3  # 🟢 حداکثر تعداد معاملات باز هم‌زمان جهت کنترل ریسک کل حساب

# 🧠 تنظیمات فاکتورهای استراتژی تکنیکال
ADX_THRESHOLD = 25
VOLUME_MA_PERIOD = 20
SWING_WINDOW = 7
RISK_REWARD_TP1 = 1.0

# 💰 🟢 فاکتورهای جدید فاز دوم: مدیریت سرمایه پویا (Money Management)
TOTAL_CAPITAL = 1000.0  # موجودی فرضی/واقعی کل حساب شما به دلار (USDT)
RISK_PERCENT = 1.0     # درصد ریسک مجاز در هر معامله (۱٪ کل سرمایه)

# 🗄️ مسیرهای دیتابیس
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

# config.py
# نسخه اصلاح‌شده v6.3 - افزایش محدودیت کندل‌ها برای تصحیح محاسبات EMA 200

import os

# لیست ارزهای مورد نظر برای اسکن چرخشی (تایم‌فریم اصلی: ۴ ساعته)
WATCHLIST = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "SUI/USDT",
    "LINK/USDT",
    "AVAX/USDT"
]

# 🛠️ اصلاح حیاتی: برای محاسبه دقیق EMA 200 حداقل به ۲۵۰ الی ۳۰۰ کندل نیاز است
CANDLES_LIMIT = 300

# تنظیمات مربوط به پلتفرم صرافی CoinEx
COINEX_API_URL = "https://api.coinex.com/v2"

# زمان‌بندی فیلتر بازگشتی برای جلوگیری از اسپم کانال (به ساعت)
TELEGRAM_LOCK_HOURS = 8

# مسیرهای دیتابیس پروژه
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

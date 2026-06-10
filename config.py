# ---------------------------------------------------------
# FILE PATH: config.py
# ---------------------------------------------------------
import os

# تعیین مسیر پایه پروژه (Root Directory)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# دیتابیس به صورت یکپارچه در ریشه پروژه قرار می‌گیرد
DB_NAME = os.path.join(BASE_DIR, "trading_bot.db")

# تنظیمات فچ دیتای صرافی
TIMEFRAME = "4h"        # تایم‌فریم مورد نیاز ربات[span_1](start_span)[span_1](end_span)
CANDLES_LIMIT = 500    # تعداد کندل‌های مورد نیاز برای تحلیل دقیق اندیکاتورها (به ویژه EMA 200)[span_2](start_span)[span_2](end_span)

# تنظیمات معاملاتی و ریسک[span_3](start_span)[span_3](end_span)
MAX_OPEN_POSITIONS = 3
ADX_THRESHOLD = 20.0
SWING_WINDOW = 5
TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 1.0

# لیست ارزهای تحت نظر[span_4](start_span)[span_4](end_span)
WATCHLIST = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "POL/USDT"]

# تنظیمات تلگرام (از متغیرهای محیطی یا مستقیم خوانده می‌شود)[span_5](start_span)[span_5](end_span)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

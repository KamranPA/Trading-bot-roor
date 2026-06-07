# ---------------------------------------------------------
# FILE PATH: /config.py
# ---------------------------------------------------------
import os

# 🪙 لیست واچ‌لیست (۱۵ ارز اصلی)
WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "LINK/USDT", 
    "AVAX/USDT", "DOGE/USDT", "ADA/USDT", "MATIC/USDT", "DOT/USDT",
    "ARB/USDT", "OP/USDT", "ATOM/USDT", "NEAR/USDT", "FTM/USDT"
]

# 📊 تنظیمات داده و تایم‌فریم
CANDLES_LIMIT = 500
TIMEFRAME = "4h"
COINEX_API_URL = "https://api.coinex.com/v2"

# 🚀 تنظیمات استراتژی ۱۰‌بعدی
SWING_WINDOW = 5                 # حیاتی برای تشخیص قله و دره (Swing)
MAX_OPEN_POSITIONS = 15          
ADX_THRESHOLD = 25               
VOLUME_CONFIRMATION_RATIO = 1.2  

# 💰 مدیریت ریسک و سرمایه
TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 0.1               
RISK_REWARD_TP1 = 1.5            # تارگت اول برای خروج پله‌ای
RISK_REWARD_TP2 = 2.5            # تارگت دوم برای سود بیشتر

# 🗄️ مسیرهای دیتابیس و تلگرام (استفاده از متغیرهای محیطی برای امنیت)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

# اطلاعات حساس (از طریق Environment Variables در گیت‌هاب خوانده می‌شود)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

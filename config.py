# ---------------------------------------------------------
# FILE PATH: config.py (v10.0 - Optimized Parameters)
# تغییرات نسبت به v9.1:
#   1. ADX_THRESHOLD: 15 → 25  (فیلتر بازار رنج - مهم‌ترین تغییر)
#   2. SWING_WINDOW: 3 → 5     (شکست‌های کاذب کمتر — ۲۰h لوک‌بک)
#   3. TP_RATIO: 1.5 → 2.0     (نسبت ریوارد به ریسک: ۲:۱ — سربه‌سر ۳۳٪)
#   4. MAX_SL_PERCENT: 0.03 → 0.05  (اجازه به ATR برای تعیین SL)
#   5. MIN_REQUIRED_SCORE: 60 → 65  (سیگنال با کیفیت‌تر)
# ---------------------------------------------------------
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# مسیرهای دیتابیس (صرفاً جهت حفظ ساختار — ربات از DATABASE_URL استفاده می‌کند)
DB_NAME            = "trading_bot.db"
DB_PATH_LIVE       = os.path.join(BASE_DIR, "data", DB_NAME)
DB_NAME_BACKTEST   = "trading_bot_backtest.db"
DB_PATH_BACKTEST   = os.path.join(BASE_DIR, "data", DB_NAME_BACKTEST)

# تنظیمات فچ دیتا
TIMEFRAME     = "4h"
CANDLES_LIMIT = 500

# مدیریت پوزیشن
MAX_OPEN_POSITIONS = 3
TOTAL_CAPITAL      = 1000.0
RISK_PERCENT       = 1.0
RISK_MULTIPLIER    = 1.0

# ── پارامترهای اصلی استراتژی ──────────────────────────────────────────────
# ADX_THRESHOLD: آستانه تشخیص روند. زیر ۲۰ = بازار رنج (sideways).
# مقدار صنعتی استاندارد: ۲۵. با ۱۵ قبلی، ربات در هر شرایطی وارد می‌شد.
ADX_THRESHOLD = 25.0

# SWING_WINDOW: تعداد کندل‌های بررسی برای تشخیص سقف/کف سوینگ.
# با ۳ (۱۲ساعت) شکست‌های کاذب زیاد بود — با ۵ (۲۰ساعت) معتبرتر.
SWING_WINDOW  = 5

# TP_RATIO: ضریب تارگت نسبت به فاصله SL.
# ۲:۱ یعنی با ۳۳٪ win rate هم به سربه‌سر می‌رسیم (قبلاً ۱.۵:۱ = نیاز به ۴۰٪).
TP_RATIO      = 2.0
SL_RATIO      = 1.0

# MAX_SL_PERCENT: سقف مجاز فاصله حد ضرر از قیمت ورود.
# با ۳٪ قبلی، SL همیشه ثابت می‌شد و ATR بی‌اثر بود (best_trade همه ۴.۵٪).
# با ۵٪، ATR در بازارهای کم‌نوسان‌تر می‌تواند SL را تعیین کند.
MAX_SL_PERCENT = 0.05

# آستانه امتیاز AI برای تایید سیگنال
AI_THRESHOLD = 65.0

# وزن‌های سیستم امتیازدهی (مجموع = ۱۰۰)
WEIGHT_AI  = 40
WEIGHT_ADX = 20
WEIGHT_RSI = 20
WEIGHT_EMA = 20

# حداقل امتیاز کل برای ورود به معامله
# با ۶۰ قبلی خیلی راحت رد می‌شد — با ۶۵ نیاز به سیگنال قوی‌تر
MIN_REQUIRED_SCORE = 65

# فیچرهای استاندارد مدل AI — تنها منبع حقیقت برای آموزش و استنتاج
AI_FEATURES = [
    'feat_adx',
    'feat_atr_percent',
    'feat_rsi',
    'feat_trend_line',
    'feat_ema_deviation',
    'feat_rsi_momentum',
    'feat_body_ratio',
]

# لیست ارزهای تحت نظر
WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "POL/USDT", "DOT/USDT", "LINK/USDT",
    "AVAX/USDT", "XRP/USDT", "LTC/USDT", "BCH/USDT",
    "ATOM/USDT",
]

# تنظیمات تلگرام
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

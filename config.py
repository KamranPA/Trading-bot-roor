# ---------------------------------------------------------
# FILE PATH: config.py (v10.3 - feat_volume_ratio added to AI_FEATURES)
# تغییرات نسبت به v10.2:
#   ✅ feat_volume_ratio به AI_FEATURES اضافه شد (8 فیچر)
#      سازگار با train_model.py v11.0، brain.py v9.1
# ---------------------------------------------------------

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────
DB_NAME = "trading_bot.db"
DB_PATH_LIVE = os.path.join(BASE_DIR, "data", DB_NAME)
DB_NAME_BACKTEST = "trading_bot_backtest.db"
DB_PATH_BACKTEST = os.path.join(BASE_DIR, "data", DB_NAME_BACKTEST)

# ─────────────────────────────────────────────────────────────
# Backtest Parameters
# ─────────────────────────────────────────────────────────────
TIMEFRAME = "4h"
CANDLES_LIMIT = 500
MAX_OPEN_POSITIONS = 999
TOTAL_CAPITAL = 1000.0
RISK_PERCENT = 1.0
RISK_MULTIPLIER = 1.0

# ─────────────────────────────────────────────────────────────
# Volume Filter
# ─────────────────────────────────────────────────────────────
ENABLE_VOLUME_FILTER = True

VOLUME_THRESHOLDS = {
    "BTCUSDT":  1000000,
    "ETHUSDT":  500000,
    "SOLUSDT":  300000,
    "DOTUSDT":  150000,
    "LINKUSDT": 200000,
    "AVAXUSDT": 250000,
    "XRPUSDT":  1000000,
    "LTCUSDT":  200000,
    "BCHUSDT":  100000,
    "ATOMUSDT": 150000,
}

# ─────────────────────────────────────────────────────────────
# Trading Parameters
# ─────────────────────────────────────────────────────────────
ADX_THRESHOLD  = 25.0
SWING_WINDOW   = 5
TP_RATIO       = 2.0
SL_RATIO       = 1.0
MAX_SL_PERCENT = 0.05

# ─────────────────────────────────────────────────────────────
# AI & Model Parameters
# ─────────────────────────────────────────────────────────────
AI_THRESHOLD      = 65.0
MIN_REQUIRED_SCORE = 65

# ─────────────────────────────────────────────────────────────
# Scoring Weights
# ─────────────────────────────────────────────────────────────
WEIGHT_AI  = 40
WEIGHT_ADX = 20
WEIGHT_RSI = 20
WEIGHT_EMA = 20

# ✅ 8 فیچر برای LightGBM (feat_volume_ratio اضافه شد)
AI_FEATURES = [
    'feat_adx',
    'feat_atr_percent',
    'feat_rsi',
    'feat_trend_line',
    'feat_ema_deviation',
    'feat_rsi_momentum',
    'feat_body_ratio',
    'feat_volume_ratio',   # v10.3: اضافه شد — حجم نسبی
]

# ─────────────────────────────────────────────────────────────
# Watchlist
# ─────────────────────────────────────────────────────────────
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "DOTUSDT", "LINKUSDT",
    "AVAXUSDT", "XRPUSDT", "LTCUSDT", "BCHUSDT", "ATOMUSDT",
]

# ─────────────────────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

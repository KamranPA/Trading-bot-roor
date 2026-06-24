# ---------------------------------------------------------
# FILE PATH: config.py (v10.2 - Volume Filter + بهبودی‌ها)
# تغییرات نسبت به v10.1:
#   - ENABLE_VOLUME_FILTER اضافه شد
#   - VOLUME_THRESHOLDS برای هر symbol
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
# ✅ Volume Filter (جدید)
# ─────────────────────────────────────────────────────────────
ENABLE_VOLUME_FILTER = True  # True = فعال ، False = غیرفعال

VOLUME_THRESHOLDS = {
    "BTCUSDT": 1000000,    # 1M
    "ETHUSDT": 500000,     # 500K
    "SOLUSDT": 300000,     # 300K
    "DOTUSDT": 150000,     # 150K
    "LINKUSDT": 200000,    # 200K
    "AVAXUSDT": 250000,    # 250K
    "XRPUSDT": 1000000,    # 1M
    "LTCUSDT": 200000,     # 200K
    "BCHUSDT": 100000,     # 100K
    "ATOMUSDT": 150000,    # 150K
}

# ─────────────────────────────────────────────────────────────
# Trading Parameters
# ─────────────────────────────────────────────────────────────
ADX_THRESHOLD = 25.0
SWING_WINDOW = 5
TP_RATIO = 2.0
SL_RATIO = 1.0
MAX_SL_PERCENT = 0.05

# ─────────────────────────────────────────────────────────────
# AI & Model Parameters
# ─────────────────────────────────────────────────────────────
AI_THRESHOLD = 65.0
MIN_REQUIRED_SCORE = 65

# ─────────────────────────────────────────────────────────────
# Scoring Weights
# ─────────────────────────────────────────────────────────────
WEIGHT_AI = 40   # AI Model (LightGBM)
WEIGHT_ADX = 20  # Trend (ADX)
WEIGHT_RSI = 20  # Momentum (RSI)
WEIGHT_EMA = 20  # Trend (EMA)

# ✅ این 7 feature برای LightGBM است (بدون volume_ratio)
AI_FEATURES = [
    'feat_adx',
    'feat_atr_percent',
    'feat_rsi',
    'feat_trend_line',
    'feat_ema_deviation',
    'feat_rsi_momentum',
    'feat_body_ratio',
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
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

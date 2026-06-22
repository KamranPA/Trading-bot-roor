# ---------------------------------------------------------
# FILE PATH: config.py (v10.1 - Volume Filter Added)
# ---------------------------------------------------------
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_NAME            = "trading_bot.db"
DB_PATH_LIVE       = os.path.join(BASE_DIR, "data", DB_NAME)
DB_NAME_BACKTEST   = "trading_bot_backtest.db"
DB_PATH_BACKTEST   = os.path.join(BASE_DIR, "data", DB_NAME_BACKTEST)

TIMEFRAME     = "4h"
CANDLES_LIMIT = 500

MAX_OPEN_POSITIONS = 3
TOTAL_CAPITAL      = 1000.0
RISK_PERCENT       = 1.0
RISK_MULTIPLIER    = 1.0

ADX_THRESHOLD  = 25.0
SWING_WINDOW   = 5
TP_RATIO       = 2.0
SL_RATIO       = 1.0
MAX_SL_PERCENT = 0.05

AI_THRESHOLD       = 65.0
MIN_REQUIRED_SCORE = 65

WEIGHT_AI  = 40
WEIGHT_ADX = 20
WEIGHT_RSI = 20
WEIGHT_EMA = 20

AI_FEATURES = [
    'feat_adx',
    'feat_atr_percent',
    'feat_rsi',
    'feat_trend_line',
    'feat_ema_deviation',
    'feat_rsi_momentum',
    'feat_body_ratio',
    'feat_volume_ratio',
]

WATCHLIST = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "DOT/USDT", "LINK/USDT",
    "AVAX/USDT", "XRP/USDT", "LTC/USDT", "BCH/USDT", "ATOM/USDT",
]

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")

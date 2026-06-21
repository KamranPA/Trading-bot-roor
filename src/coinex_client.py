# ---------------------------------------------------------
# FILE PATH: src/coinex_client.py  (v2.0 - Direct REST API)
# تغییرات:
#   - حذف ccxt (که ممکن بود با نسخه‌های جدید break شود)
#   - استفاده مستقیم از CoinEx REST API v2
#   - تبدیل فرمت جفت‌ارز: BTC/USDT → BTCUSDT
#   - retry داخلی (3 بار) با backoff
# ---------------------------------------------------------
import time
import logging
import requests
import pandas as pd

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.coinex.com/v2/spot/kline"

_TF_MAP = {
    "1m":  "1min",
    "5m":  "5min",
    "15m": "15min",
    "30m": "30min",
    "1h":  "1hour",
    "2h":  "2hour",
    "4h":  "4hour",
    "6h":  "6hour",
    "12h": "12hour",
    "1d":  "1day",
    "1w":  "1week",
}

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "TradingBot/2.0",
    "Accept": "application/json",
})


def _pair_to_market(pair: str) -> str:
    """BTC/USDT  →  BTCUSDT"""
    return pair.replace("/", "").replace("-", "").upper()


def get_coinex_candles(pair: str, timeframe: str = "4h", limit: int = 500) -> pd.DataFrame | None:
    """
    دریافت کندل‌های OHLCV از CoinEx REST API v2.
    در صورت خطا سه بار تلاش می‌کند سپس None برمی‌گرداند.
    """
    market = _pair_to_market(pair)
    period = _TF_MAP.get(timeframe, timeframe)
    # CoinEx v2 حداکثر ۱۰۰۰ کندل در یک درخواست می‌دهد
    req_limit = min(limit, 1000)

    params = {"market": market, "period": period, "limit": req_limit}

    for attempt in range(1, 4):
        try:
            resp = _SESSION.get(_BASE_URL, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                logger.warning("CoinEx API خطا برای %s: code=%s msg=%s",
                               pair, data.get("code"), data.get("message"))
                return None

            candles = data.get("data", [])
            if not candles:
                logger.warning("CoinEx: داده‌ای برای %s دریافت نشد", pair)
                return None

            df = pd.DataFrame(candles)
            # ستون‌های API v2: created_at, open, high, low, close, volume, value
            df.rename(columns={
                "created_at": "Timestamp",
                "open":       "Open",
                "high":       "High",
                "low":        "Low",
                "close":      "Close",
                "volume":     "Volume",
            }, inplace=True)

            for col in ["Open", "High", "Low", "Close", "Volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df.sort_values("Timestamp", inplace=True)
            df.reset_index(drop=True, inplace=True)

            logger.info("✅ %d کندل برای %s دریافت شد", len(df), pair)
            return df

        except requests.exceptions.RequestException as e:
            logger.warning("تلاش %d/3 برای %s ناموفق: %s", attempt, pair, e)
            if attempt < 3:
                time.sleep(2 * attempt)

    logger.error("❌ دریافت کندل برای %s بعد از ۳ تلاش ناموفق بود", pair)
    return None

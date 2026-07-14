# FILE PATH: src/momentum_strategy.py (v1.0 - NEW)
# ---------------------------------------------------------------------------
# استراتژی Daily Momentum — بر پایه‌ی ادبیات آکادمیک مستند (Liu & Tsyvinski/
# NBER؛ Liu et al. 2022؛ "A Decade of Evidence of Trend Following in Crypto").
#
# ⚠️ نکات طراحی مهم که باید حفظ شوند (نتیجه‌ی هفته‌ها تست walk-forward):
#   1. پارامتر ثابت است — LOOKBACK=21, HOLD=5 — و هرگز نباید خودکار
#      بازآموزی/بازانتخاب شود. تست‌ها نشان دادند بازانتخاب پارامتر روی
#      بازه‌های کوچک، خودش منبع نویز/overfitting است؛ نسخه‌ی ثابت پایدارتر
#      و قابل‌اعتمادتر بود.
#   2. فقط BTC/USDT و ETH/USDT — تست‌ها نشان دادند SOL/XRP/LTC edge
#      نداشتند (منفی بودند). این را گسترش نده بدون تست walk-forward مجدد.
#   3. بدون Stop-Loss — دقیقاً همان چیزی که تست و تأیید شد (نگه‌داری ثابت
#      ۵ روزه) پیاده می‌شود. اضافه‌کردن SL یعنی اجرای چیزی متفاوت از آنچه
#      اعتبارسنجی شده.
#   4. edge وابسته به رژیم بازار است (walk-forward نشان داد ۲ از ۳ بازه‌ی
#      تاریخی مثبت بود، نه هر ۳) — انتظار دوره‌های رکود واقعی را داشته باش.
# ---------------------------------------------------------------------------
import logging
from datetime import date, timedelta

from src import coinex_client

logger = logging.getLogger(__name__)

# ✅ پارامتر ثابت — نتیجه‌ی اعتبارسنجی‌شده، تغییرش نده بدون تست walk-forward مجدد
MOMENTUM_SYMBOLS = ['BTCUSDT', 'ETHUSDT']
LOOKBACK_DAYS = 21
HOLD_DAYS = 5
MIN_THRESHOLD_PCT = 0.0


def _fetch_daily_closes(symbol: str, limit: int = 60):
    """دریافت قیمت‌های بسته‌شدن روزانه (کافی برای LOOKBACK=21 + حاشیه‌ی اطمینان)."""
    df = coinex_client.get_coinex_candles(symbol, timeframe="1d", limit=limit)
    if df is None or df.empty:
        return None
    df = df.sort_values('Timestamp' if 'Timestamp' in df.columns else df.columns[0]).reset_index(drop=True)
    return df


def generate_momentum_signal(symbol: str) -> dict | None:
    """
    تولید سیگنال momentum برای یک ارز بر اساس آخرین کندل روزانه‌ی بسته‌شده.

    Returns:
        dict با کلیدهای direction/entry_price/momentum_return_pct/
        planned_exit_date، یا None اگر سیگنالی نباشد یا داده کافی نباشد.
    """
    df = _fetch_daily_closes(symbol, limit=LOOKBACK_DAYS + 10)
    if df is None or len(df) < LOOKBACK_DAYS + 1:
        logger.warning(f"{symbol}: داده‌ی روزانه کافی نیست برای momentum")
        return None

    close_col = 'Close' if 'Close' in df.columns else 'close'
    close_now = float(df.iloc[-1][close_col])
    close_lookback = float(df.iloc[-1 - LOOKBACK_DAYS][close_col])
    if close_lookback == 0:
        return None

    momentum_return_pct = (close_now - close_lookback) / close_lookback * 100

    direction = None
    if momentum_return_pct >= MIN_THRESHOLD_PCT:
        direction = 'LONG'
    elif momentum_return_pct <= -MIN_THRESHOLD_PCT:
        direction = 'SHORT'

    if direction is None:
        return None

    today = date.today()
    return {
        'pair': symbol,
        'direction': direction,
        'entry_price': close_now,
        'entry_date': today,
        'planned_exit_date': today + timedelta(days=HOLD_DAYS),
        'lookback_days': LOOKBACK_DAYS,
        'hold_days': HOLD_DAYS,
        'momentum_return_pct': round(momentum_return_pct, 4),
    }


def get_current_price(symbol: str) -> float | None:
    """قیمت لحظه‌ای (آخرین کندل روزانه) برای بستن پوزیشن در تاریخ برنامه‌ریزی‌شده."""
    df = _fetch_daily_closes(symbol, limit=3)
    if df is None or df.empty:
        return None
    close_col = 'Close' if 'Close' in df.columns else 'close'
    return float(df.iloc[-1][close_col])

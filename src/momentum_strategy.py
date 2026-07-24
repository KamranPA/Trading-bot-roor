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

# ✅ NEW: شبیه‌سازی معامله‌ی فرضی برای محاسبه‌ی سود/ضرر واقعی‌تر
POSITION_SIZE_USD = 100.0
LEVERAGE = 5.0

# ⚠️ نکته‌ی حیاتی: این استراتژی عمداً بدون Stop-Loss طراحی و تست شده
# (نگه‌داری ثابت ۵ روزه). ولی با لوریج ۵، یک حرکت ۱/LEVERAGE=۲۰٪ خلاف
# جهت پوزیشن، کل مارجین را از بین می‌برد (لیکویید شدن) — این می‌تواند
# زودتر از تاریخ خروج برنامه‌ریزی‌شده اتفاق بیفتد. به همین دلیل
# momentum_bot.py باید هر روز (نه فقط روز خروج) ریسک لیکویید شدن را
# چک کند، وگرنه PnL محاسبه‌شده با واقعیت صرافی هم‌خوانی نخواهد داشت.
# این مقدار یک تقریب ساده است (نادیده‌گرفتن کارمزد فاندینگ/margin
# maintenance دقیق صرافی)، نه محاسبه‌ی دقیق صرافی‌محور.
LIQUIDATION_MOVE_PCT = 100.0 / LEVERAGE  # = 20.0% برای لوریج ۵


def compute_leveraged_pnl_usd(price_pnl_pct: float, position_size_usd: float = POSITION_SIZE_USD,
                               leverage: float = LEVERAGE) -> float:
    """
    تبدیل بازده درصدی قیمت (price_pnl_pct، مثبت یا منفی) به سود/ضرر دلاری
    روی یک پوزیشن فرضی با مارجین position_size_usd و لوریج leverage.
    مثال: قیمت ۳٪ حرکت کرد، مارجین=۱۰۰$، لوریج=۵ → ۱۰۰*۵*۰.۰۳ = ۱۵$ سود.
    """
    return round(position_size_usd * leverage * (price_pnl_pct / 100.0), 2)


def get_liquidation_price(entry_price: float, direction: str, leverage: float = LEVERAGE) -> float:
    """قیمتی که در آن (تقریباً) کل مارجین از بین می‌رود — ساده‌سازی‌شده،
    بدون احتساب کارمزد/margin maintenance دقیق صرافی."""
    move_fraction = 1.0 / leverage
    if direction == 'LONG':
        return entry_price * (1.0 - move_fraction)
    else:
        return entry_price * (1.0 + move_fraction)


def get_current_day_ohlc(symbol: str) -> dict | None:
    """High/Low/Close آخرین کندل روزانه‌ی بسته‌شده — برای چک روزانه‌ی
    ریسک لیکویید شدن (نه فقط قیمت لحظه‌ای بسته‌شدن)."""
    df = _fetch_daily_closes(symbol, limit=3)
    if df is None or df.empty:
        return None
    row = df.iloc[-1]
    high_col = 'High' if 'High' in df.columns else 'high'
    low_col = 'Low' if 'Low' in df.columns else 'low'
    close_col = 'Close' if 'Close' in df.columns else 'close'
    return {
        'high': float(row[high_col]),
        'low': float(row[low_col]),
        'close': float(row[close_col]),
    }


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
    liquidation_price = get_liquidation_price(close_now, direction, LEVERAGE)
    return {
        'pair': symbol,
        'direction': direction,
        'entry_price': close_now,
        'entry_date': today,
        'planned_exit_date': today + timedelta(days=HOLD_DAYS),
        'lookback_days': LOOKBACK_DAYS,
        'hold_days': HOLD_DAYS,
        'momentum_return_pct': round(momentum_return_pct, 4),
        'position_size_usd': POSITION_SIZE_USD,
        'leverage': LEVERAGE,
        'liquidation_price': round(liquidation_price, 6),
    }


def get_current_price(symbol: str) -> float | None:
    """قیمت لحظه‌ای (آخرین کندل روزانه) برای بستن پوزیشن در تاریخ برنامه‌ریزی‌شده."""
    df = _fetch_daily_closes(symbol, limit=3)
    if df is None or df.empty:
        return None
    close_col = 'Close' if 'Close' in df.columns else 'close'
    return float(df.iloc[-1][close_col])

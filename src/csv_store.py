# ---------------------------------------------------------
# FILE PATH: src/csv_store.py  (NEW MODULE)
# مدیریت ذخیره و خواندن داده‌های بکتست از CSV
# جایگزین SQLite محلی برای بکتست — سازگار با ساختار موجود
# ---------------------------------------------------------
import os
import csv
import logging
from datetime import datetime, timezone

import pandas as pd


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

logger = logging.getLogger(__name__)

# مسیر پیش‌فرض فایل‌های CSV
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')

BACKTEST_TRADES_CSV   = os.path.join(_DATA_DIR, 'backtest_trades.csv')
BACKTEST_SUMMARY_CSV  = os.path.join(_DATA_DIR, 'backtest_table_summary.csv')

# ستون‌های استاندارد
TRADE_COLUMNS = [
    'id', 'pair', 'direction', 'entry_price', 'stop_loss',
    'tp1', 'tp2', 'close_price', 'pnl_percent',
    'entry_time', 'close_time', 'status',
    'ai_score', 'total_score', 'feat_adx', 'feat_rsi',
    'feat_ema_deviation', 'feat_atr_percent',
]

SUMMARY_COLUMNS = [
    'pair', 'total_trades', 'win_trades', 'loss_trades',
    'win_rate', 'avg_pnl', 'total_pnl', 'max_drawdown',
    'best_trade', 'worst_trade', 'updated_at',
]


def _ensure_dir():
    os.makedirs(_DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# نوشتن معامله
# ---------------------------------------------------------------------------

def save_backtest_trade(trade: dict) -> bool:
    """
    یک معامله بکتست را به CSV اضافه می‌کند.

    Args:
        trade: دیکشنری با کلیدهای TRADE_COLUMNS

    Returns:
        True در صورت موفقیت
    """
    _ensure_dir()
    file_exists = os.path.isfile(BACKTEST_TRADES_CSV)
    try:
        with open(BACKTEST_TRADES_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=TRADE_COLUMNS, extrasaction='ignore')
            if not file_exists:
                writer.writeheader()
            # مقادیر پیش‌فرض برای فیلدهای ضروری
            trade.setdefault('id',         _next_id())
            trade.setdefault('entry_time', _utcnow_iso())
            trade.setdefault('status',     'OPEN')
            writer.writerow(trade)
        return True
    except Exception as e:
        logger.error("خطا در ذخیره معامله بکتست: %s", e)
        return False


def close_backtest_trade(trade_id, close_price: float, status: str = 'CLOSED') -> bool:
    """
    یک معامله باز را با قیمت بسته‌شدن به‌روزرسانی می‌کند.

    Args:
        trade_id: شناسه معامله
        close_price: قیمت بسته‌شدن
        status: 'CLOSED' یا 'SL_HIT' یا 'TP_HIT'
    """
    _ensure_dir()
    if not os.path.isfile(BACKTEST_TRADES_CSV):
        logger.warning("فایل بکتست یافت نشد: %s", BACKTEST_TRADES_CSV)
        return False
    try:
        df = pd.read_csv(BACKTEST_TRADES_CSV)
        mask = df['id'] == trade_id
        if not mask.any():
            logger.warning("معامله با id=%s یافت نشد", trade_id)
            return False

        row = df[mask].iloc[0]
        entry  = float(row['entry_price'])
        direction = str(row['direction'])

        # محاسبه PnL
        if direction == 'LONG':
            pnl = ((close_price - entry) / entry) * 100
        else:
            pnl = ((entry - close_price) / entry) * 100

        df.loc[mask, 'close_price'] = round(close_price, 6)
        df.loc[mask, 'pnl_percent'] = round(pnl, 4)
        df.loc[mask, 'status']      = status
        df.loc[mask, 'close_time']  = _utcnow_iso()

        df.to_csv(BACKTEST_TRADES_CSV, index=False, encoding='utf-8')
        logger.debug("معامله %s بسته شد — PnL: %.2f%%", trade_id, pnl)
        return True
    except Exception as e:
        logger.error("خطا در بستن معامله بکتست %s: %s", trade_id, e)
        return False


# ---------------------------------------------------------------------------
# خواندن معاملات
# ---------------------------------------------------------------------------

def load_backtest_trades(pair: str = None, status: str = None) -> pd.DataFrame:
    """
    معاملات بکتست را بارگذاری می‌کند.

    Args:
        pair: فیلتر ارز (اختیاری)
        status: فیلتر وضعیت مثل 'CLOSED' (اختیاری)

    Returns:
        DataFrame با ستون‌های TRADE_COLUMNS
    """
    if not os.path.isfile(BACKTEST_TRADES_CSV):
        logger.info("فایل بکتست وجود ندارد — DataFrame خالی برمی‌گردد")
        return pd.DataFrame(columns=TRADE_COLUMNS)
    try:
        df = pd.read_csv(BACKTEST_TRADES_CSV, encoding='utf-8')
        if pair:
            df = df[df['pair'] == pair]
        if status:
            df = df[df['status'] == status]
        return df.reset_index(drop=True)
    except Exception as e:
        logger.error("خطا در بارگذاری CSV بکتست: %s", e)
        return pd.DataFrame(columns=TRADE_COLUMNS)


# ---------------------------------------------------------------------------
# تولید خلاصه (Summary)
# ---------------------------------------------------------------------------

def generate_summary(df_trades: pd.DataFrame = None) -> pd.DataFrame:
    """
    خلاصه عملکرد هر ارز را محاسبه و در BACKTEST_SUMMARY_CSV ذخیره می‌کند.

    Args:
        df_trades: دیتافریم معاملات (اگر None باشد از CSV خوانده می‌شود)

    Returns:
        DataFrame خلاصه
    """
    if df_trades is None:
        df_trades = load_backtest_trades(status='CLOSED')

    if df_trades.empty:
        logger.info("هیچ معامله بسته‌ای برای خلاصه‌سازی وجود ندارد.")
        return pd.DataFrame(columns=SUMMARY_COLUMNS)

    rows = []
    for pair, group in df_trades.groupby('pair'):
        pnls        = group['pnl_percent'].dropna()
        total       = len(group)
        wins        = int((pnls > 0).sum())
        losses      = int((pnls <= 0).sum())
        win_rate    = round(wins / total * 100, 1) if total > 0 else 0.0
        avg_pnl     = round(pnls.mean(), 2) if len(pnls) else 0.0
        total_pnl   = round(pnls.sum(), 2)

        # محاسبه Max Drawdown ساده
        cumulative  = (1 + pnls / 100).cumprod()
        rolling_max = cumulative.cummax()
        drawdown    = ((cumulative - rolling_max) / rolling_max * 100)
        max_dd      = round(drawdown.min(), 2) if len(drawdown) else 0.0

        rows.append({
            'pair':         pair,
            'total_trades': total,
            'win_trades':   wins,
            'loss_trades':  losses,
            'win_rate':     win_rate,
            'avg_pnl':      avg_pnl,
            'total_pnl':    total_pnl,
            'max_drawdown': max_dd,
            'best_trade':   round(pnls.max(), 2) if len(pnls) else 0.0,
            'worst_trade':  round(pnls.min(), 2) if len(pnls) else 0.0,
            'updated_at':   _utcnow_iso(),
        })

    summary_df = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
    _ensure_dir()
    try:
        summary_df.to_csv(BACKTEST_SUMMARY_CSV, index=False, encoding='utf-8')
        logger.info("✅ خلاصه بکتست ذخیره شد: %s", BACKTEST_SUMMARY_CSV)
    except Exception as e:
        logger.error("خطا در ذخیره خلاصه: %s", e)

    return summary_df


# ---------------------------------------------------------------------------
# صادرکردن به SQLite  (برای workflow و آپلود artifact)
# ---------------------------------------------------------------------------

def export_to_sqlite(db_path: str = None) -> bool:
    """
    داده‌های بکتست (معاملات + خلاصه) را در یک فایل SQLite ذخیره می‌کند.
    مسیر پیش‌فرض: data/trading_bot_backtest.db

    این تابع در پایان run_all_backtests() فراخوانی می‌شود
    تا workflow بتواند فایل .db را git add و upload کند.
    """
    import sqlite3

    if db_path is None:
        db_path = os.path.join(_DATA_DIR, 'trading_bot_backtest.db')

    _ensure_dir()

    try:
        trades_df  = load_backtest_trades()
        closed_df  = trades_df[trades_df['status'] != 'OPEN'].copy() if not trades_df.empty else None
        summary_df = generate_summary(closed_df)

        with sqlite3.connect(db_path) as conn:
            # جدول معاملات
            if not trades_df.empty:
                trades_df.to_sql('backtest_trades', conn,
                                 if_exists='replace', index=False)
            else:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS backtest_trades ("
                    + ', '.join(f'{c} TEXT' for c in TRADE_COLUMNS)
                    + ")"
                )

            # جدول خلاصه
            if not summary_df.empty:
                summary_df.to_sql('backtest_summary', conn,
                                  if_exists='replace', index=False)
            else:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS backtest_summary ("
                    + ', '.join(f'{c} TEXT' for c in SUMMARY_COLUMNS)
                    + ")"
                )

            conn.commit()

        logger.info("✅ SQLite ذخیره شد: %s", db_path)
        return True

    except Exception as e:
        logger.error("export_to_sqlite خطا: %s", e)
        return False


# ---------------------------------------------------------------------------
# کمکی‌ها
# ---------------------------------------------------------------------------

def _next_id() -> int:
    """شناسه بعدی بر اساس تعداد ردیف‌های موجود"""
    if not os.path.isfile(BACKTEST_TRADES_CSV):
        return 1
    try:
        with open(BACKTEST_TRADES_CSV, 'r', encoding='utf-8') as f:
            return sum(1 for _ in f)  # شامل هدر — کافی برای یکتایی
    except Exception:
        return 1


def get_open_trades_count() -> int:
    """تعداد معاملات باز بکتست"""
    df = load_backtest_trades(status='OPEN')
    return len(df)


def get_closed_trades_count(pair: str = None) -> int:
    """تعداد معاملات بسته"""
    df = load_backtest_trades(pair=pair, status='CLOSED')
    return len(df)

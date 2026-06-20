# ---------------------------------------------------------
# FILE PATH: src/database.py  (FIXED & IMPROVED v2.0)
# دیتابیس ابری Supabase / PostgreSQL
#
# تغییرات نسبت به نسخه قبلی:
#   1. تابع جدید get_total_closed_positions_count() — برای خودارتقایی
#   2. اصلاح get_last_signal_for_pair: مقایسه timestamp با timezone-aware
#   3. init_db: ساخت تمام جدول‌های لازم در یک تراکنش
#   4. save_signal_advanced: اعتبارسنجی direction قبل از درج
#   5. بررسی DATABASE_URL در زمان اتصال (نه import) تا importهای جانبی کرش نکنند
#   6. تمام توابع دارای logging و try/except مستقل
# ---------------------------------------------------------
import os
import logging
import datetime
from contextlib import contextmanager

try:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import OperationalError, InterfaceError
except ImportError:
    raise ImportError(
        "psycopg2 نصب نشده است. اجرا کنید: pip install psycopg2-binary"
    )

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# اتصال به دیتابیس
# ---------------------------------------------------------------------------

def _get_database_url() -> str:
    """خواندن DATABASE_URL در زمان نیاز — تا import این ماژول کرش نکند."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise EnvironmentError(
            "متغیر محیطی DATABASE_URL تنظیم نشده است.\n"
            "مثال: postgresql://user:pass@host:5432/dbname"
        )
    return url


def _get_connection():
    """اتصال جدید به PostgreSQL — برای هر عملیات مستقل"""
    try:
        conn = psycopg2.connect(_get_database_url(), connect_timeout=10)
        conn.autocommit = False
        return conn
    except OperationalError as e:
        logger.critical("اتصال به دیتابیس ناموفق: %s", e)
        raise


def get_connection():
    """اتصال عمومی به دیتابیس (برای اسکریپت‌های جانبی مثل تست اتصال و آنالیز)."""
    return _get_connection()


@contextmanager
def _db():
    """Context manager برای اتصال + commit/rollback خودکار"""
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("تراکنش برگشت خورد: %s", e)
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# راه‌اندازی جدول‌ها
# ---------------------------------------------------------------------------

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS signals (
    id              SERIAL PRIMARY KEY,
    pair            VARCHAR(20)  NOT NULL,
    direction       VARCHAR(10)  CHECK (direction IN ('LONG', 'SHORT')),
    entry_price     NUMERIC(20, 8),
    stop_loss       NUMERIC(20, 8),
    tp1             NUMERIC(20, 8),
    tp2             NUMERIC(20, 8),
    swing_ref       NUMERIC(20, 8),
    status          VARCHAR(20)  DEFAULT 'OPEN',
    pnl_percent     NUMERIC(10, 4),
    close_price     NUMERIC(20, 8),
    feat_adx        NUMERIC(10, 4),
    feat_rsi        NUMERIC(10, 4),
    feat_rsi_momentum   NUMERIC(10, 4),
    feat_ema_deviation  NUMERIC(10, 4),
    feat_atr_percent    NUMERIC(10, 4),
    feat_trend_line     NUMERIC(10, 4),
    feat_body_ratio     NUMERIC(10, 4),
    total_score     NUMERIC(8, 2),
    ai_score        NUMERIC(8, 2),
    rsi_score       NUMERIC(8, 2),
    adx_score       NUMERIC(8, 2),
    ema_score       NUMERIC(8, 2),
    timestamp       TIMESTAMPTZ  DEFAULT NOW(),
    close_time      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_signals_pair      ON signals (pair);
CREATE INDEX IF NOT EXISTS idx_signals_status    ON signals (status);
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals (timestamp DESC);

CREATE TABLE IF NOT EXISTS scan_log (
    id          SERIAL PRIMARY KEY,
    pair        VARCHAR(20)  NOT NULL,
    status      VARCHAR(30)  NOT NULL,
    total_score NUMERIC(8, 2),
    ai_score    NUMERIC(8, 2),
    rsi_score   NUMERIC(8, 2),
    adx_score   NUMERIC(8, 2),
    ema_score   NUMERIC(8, 2),
    scanned_at  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scan_log_pair ON scan_log (pair);
CREATE INDEX IF NOT EXISTS idx_scan_log_at   ON scan_log (scanned_at DESC);
"""


def init_db() -> None:
    """
    ساخت جدول‌های لازم در صورت عدم وجود.
    ایمن برای اجرای مکرر (idempotent).
    """
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(_INIT_SQL)
        logger.info("✅ init_db: جدول‌های دیتابیس آماده هستند.")
    except Exception as e:
        logger.critical("init_db ناموفق: %s", e)
        raise


# ---------------------------------------------------------------------------
# ذخیره سیگنال
# ---------------------------------------------------------------------------

_SIGNAL_COLUMNS = (
    'pair', 'direction', 'entry_price', 'stop_loss', 'tp1', 'tp2', 'swing_ref',
    'feat_adx', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line',
    'feat_ema_deviation', 'feat_rsi_momentum', 'feat_body_ratio',
    'total_score', 'ai_score', 'rsi_score', 'adx_score', 'ema_score',
)


def save_signal_advanced(pair: str, **kwargs) -> int | None:
    """
    ذخیره سیگنال جدید در جدول signals.

    Args:
        pair: نماد ارز
        **kwargs: فیلدهای اضافی (direction, entry_price, stop_loss, ...)

    Returns:
        id ردیف جدید یا None در صورت خطا
    """
    direction = kwargs.get('direction')
    if direction not in ('LONG', 'SHORT'):
        logger.warning("save_signal_advanced: direction نامعتبر '%s' برای %s — ذخیره لغو شد", direction, pair)
        return None

    data = {'pair': pair}
    for col in _SIGNAL_COLUMNS:
        if col != 'pair' and col in kwargs:
            data[col] = kwargs[col]

    cols   = ', '.join(data.keys())
    placeholders = ', '.join(['%s'] * len(data))
    sql    = f"INSERT INTO signals ({cols}) VALUES ({placeholders}) RETURNING id"

    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, list(data.values()))
                row = cur.fetchone()
                new_id = row[0] if row else None
        logger.info("سیگنال ذخیره شد | pair=%s direction=%s id=%s", pair, direction, new_id)
        return new_id
    except Exception as e:
        logger.error("save_signal_advanced خطا برای %s: %s", pair, e)
        return None


# ---------------------------------------------------------------------------
# پوزیشن‌های باز
# ---------------------------------------------------------------------------

def get_open_positions() -> list[dict]:
    """
    لیست همه پوزیشن‌های باز (status='OPEN').

    Returns:
        لیستی از دیکشنری با کلیدهای: id, symbol, direction, entry_price, stop_loss, tp1, tp2
    """
    sql = """
        SELECT id, pair AS symbol, direction,
               entry_price, stop_loss, tp1, tp2, timestamp
        FROM signals
        WHERE status = 'OPEN'
        ORDER BY timestamp ASC
    """
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error("get_open_positions خطا: %s", e)
        return []


def get_open_positions_count() -> int:
    """تعداد پوزیشن‌های باز — برای کنترل MAX_OPEN_POSITIONS"""
    sql = "SELECT COUNT(*) FROM signals WHERE status = 'OPEN'"
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                result = cur.fetchone()
        return int(result[0]) if result else 0
    except Exception as e:
        logger.error("get_open_positions_count خطا: %s", e)
        return 0


def get_total_closed_positions_count() -> int:
    """
    تعداد کل پوزیشن‌های بسته‌شده — برای تریگر خودارتقایی (هر ۵۰ معامله).

    این تابع در نسخه قبلی وجود نداشت و در main.py اضافه شد.
    """
    sql = "SELECT COUNT(*) FROM signals WHERE status = 'CLOSED'"
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                result = cur.fetchone()
        return int(result[0]) if result else 0
    except Exception as e:
        logger.error("get_total_closed_positions_count خطا: %s", e)
        return 0


def update_position_status(
    signal_id: int,
    new_status: str,
    pnl_percent: float,
    close_price: float | None = None,
) -> bool:
    """
    به‌روزرسانی وضعیت پوزیشن پس از بسته‌شدن.

    Args:
        signal_id:   id ردیف در جدول signals
        new_status:  'CLOSED' | 'SL_HIT' | 'TP_HIT'
        pnl_percent: سود/ضرر به درصد (مثبت = سود)
        close_price: قیمت بسته‌شدن (اختیاری)

    Returns:
        True در صورت موفقیت
    """
    sql = """
        UPDATE signals
        SET status      = %s,
            pnl_percent = %s,
            close_price = %s,
            close_time  = NOW()
        WHERE id = %s AND status = 'OPEN'
    """
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (new_status, round(pnl_percent, 4), close_price, signal_id))
                updated = cur.rowcount
        if updated == 0:
            logger.warning("update_position_status: id=%s یافت نشد یا قبلاً بسته شده", signal_id)
            return False
        logger.debug("پوزیشن %s → %s | PnL: %.2f%%", signal_id, new_status, pnl_percent)
        return True
    except Exception as e:
        logger.error("update_position_status خطا برای id=%s: %s", signal_id, e)
        return False


# ---------------------------------------------------------------------------
# آخرین سیگنال یک ارز — برای فیلتر ۸ ساعته
# ---------------------------------------------------------------------------

def get_last_signal_for_pair(pair: str) -> dict | None:
    """
    آخرین سیگنال ثبت‌شده برای یک ارز (صرف‌نظر از وضعیت).

    Returns:
        دیکشنری با کلیدهای direction و timestamp (timezone-aware UTC)
        یا None اگر سیگنالی وجود نداشته باشد
    """
    sql = """
        SELECT direction, timestamp
        FROM signals
        WHERE pair = %s
        ORDER BY timestamp DESC
        LIMIT 1
    """
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (pair,))
                row = cur.fetchone()
        if not row:
            return None

        result = dict(row)

        # FIX: اطمینان از timezone-aware بودن timestamp برای مقایسه درست
        ts = result.get('timestamp')
        if ts and isinstance(ts, datetime.datetime):
            if ts.tzinfo is None:
                # اگر naive بود، UTC فرض می‌کنیم
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            result['timestamp'] = ts

        return result
    except Exception as e:
        logger.error("get_last_signal_for_pair خطا برای %s: %s", pair, e)
        return None


# ---------------------------------------------------------------------------
# لاگ اسکن
# ---------------------------------------------------------------------------

def log_scan_status(
    pair: str,
    status: str,
    total: float = 0.0,
    ai: float = 0.0,
    rsi: float = 0.0,
    adx: float = 0.0,
    ema: float = 0.0,
) -> None:
    """
    ثبت نتیجه اسکن هر ارز در جدول scan_log.
    در صورت خطا، سکوت می‌کند (اسکن‌های اصلی متوقف نمی‌شوند).
    """
    sql = """
        INSERT INTO scan_log (pair, status, total_score, ai_score, rsi_score, adx_score, ema_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (pair, status,
                                  round(total, 2), round(ai, 2),
                                  round(rsi, 2),   round(adx, 2),
                                  round(ema, 2)))
    except Exception as e:
        logger.warning("log_scan_status خطا برای %s: %s", pair, e)


# ---------------------------------------------------------------------------
# کمکی — آمار کلی (برای Heartbeat / گزارش)
# ---------------------------------------------------------------------------

def get_performance_summary() -> dict:
    """
    آمار خلاصه برای ارسال در Heartbeat:
    تعداد پوزیشن‌های باز، کل بسته‌شده، Win Rate، مجموع PnL
    """
    sql = """
        SELECT
            COUNT(*) FILTER (WHERE status = 'OPEN')                          AS open_count,
            COUNT(*) FILTER (WHERE status = 'CLOSED')                        AS closed_count,
            COUNT(*) FILTER (WHERE status = 'CLOSED' AND pnl_percent > 0)    AS win_count,
            ROUND(AVG(pnl_percent) FILTER (WHERE status = 'CLOSED'), 2)      AS avg_pnl,
            ROUND(SUM(pnl_percent) FILTER (WHERE status = 'CLOSED'), 2)      AS total_pnl
        FROM signals
    """
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                row = cur.fetchone()
        if not row:
            return {}
        data = dict(row)
        closed = data.get('closed_count') or 0
        wins   = data.get('win_count')   or 0
        data['win_rate'] = round(wins / closed * 100, 1) if closed > 0 else 0.0
        return data
    except Exception as e:
        logger.error("get_performance_summary خطا: %s", e)
        return {}


def get_recent_scan_logs(limit: int = 50) -> list[dict]:
    """
    آخرین لاگ‌های اسکن — برای دیباگ و مانیتورینگ.
    """
    sql = """
        SELECT pair, status, total_score, ai_score, scanned_at
        FROM scan_log
        ORDER BY scanned_at DESC
        LIMIT %s
    """
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (limit,))
                rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error("get_recent_scan_logs خطا: %s", e)
        return []


def get_signals_for_pair(pair: str, status: str = None, limit: int = 100) -> list[dict]:
    """
    سیگنال‌های یک ارز خاص — برای optimizer و آنالیز.

    Args:
        pair:   نماد ارز
        status: فیلتر وضعیت (اختیاری)
        limit:  حداکثر تعداد نتایج
    """
    where = "WHERE pair = %s"
    args  = [pair]
    if status:
        where += " AND status = %s"
        args.append(status)

    sql = f"""
        SELECT id, direction, entry_price, stop_loss, tp1, tp2,
               pnl_percent, status, timestamp, close_time,
               total_score, ai_score
        FROM signals
        {where}
        ORDER BY timestamp DESC
        LIMIT %s
    """
    args.append(limit)

    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, args)
                rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error("get_signals_for_pair خطا برای %s: %s", pair, e)
        return []

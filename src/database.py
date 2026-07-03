# ---------------------------------------------------------------------------
# FILE PATH: src/database.py  (v3.3 - Connection pooling for internal calls)
# تغییرات نسبت به v3.2:
#   ✅ FIX: توابع داخلی این فایل (از طریق context manager _db) حالا از یک
#      ThreadedConnectionPool مشترک استفاده می‌کنند، نه این‌که هر فراخوانی
#      یک اتصال جدید psycopg2 باز/بسته کند. با ThreadPoolExecutor(12) در
#      main.py که هم‌زمان روی چند ارز کار می‌کند، این از فشار زیاد روی
#      سقف اتصالات همزمان دیتابیس (خصوصاً پلن‌های رایگان Postgres/Supabase)
#      جلوگیری می‌کند.
#   ⚠️ get_connection() عمداً pool نشده باقی مانده — چون ممکن است اسکریپت‌های
#      بیرونی (مثل test_db.py) مستقیم از آن استفاده کنند و خودشان conn.close()
#      را صدا بزنند؛ اگر آن را هم pool می‌کردیم، close() به‌جای برگرداندن
#      اتصال به pool، آن را واقعاً می‌بست و اتصال را از pool حذف می‌کرد.
#      اگر test_db.py یا اسکریپت دیگری زیاد صدا زده می‌شود، بهتر است آن را
#      هم به‌صراحت به همین pool مهاجرت دهی (با putconn به‌جای close).
# ---------------------------------------------------------------------------
import os
import logging
import datetime
import threading
from contextlib import contextmanager

try:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import OperationalError
    from psycopg2 import pool as _pg_pool
except ImportError:
    raise ImportError("psycopg2 نصب نشده است. اجرا کنید: pip install psycopg2-binary")

logger = logging.getLogger(__name__)


def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise EnvironmentError("متغیر محیطی DATABASE_URL تنظیم نشده است.")
    if "sslmode" not in url:
        url = url + ("&" if "?" in url else "?") + "sslmode=require"
    return url


def _get_connection():
    """اتصال مستقیم و غیر Pool شده — برای استفاده‌ی توابع داخلی همین ماژول
    (از طریق _get_pool) یا برای فراخوانی مستقیم بیرونی (get_connection)."""
    try:
        conn = psycopg2.connect(_get_database_url(), connect_timeout=15)
        conn.autocommit = False
        return conn
    except OperationalError as e:
        logger.critical("اتصال به دیتابیس ناموفق: %s", e)
        raise


def get_connection():
    """
    اتصال مستقل (غیر Pool شده) — برای استفاده‌ی مستقیم بیرون از این ماژول
    (مثل test_db.py). فراخوان مسئول conn.close() خودش است.
    """
    return _get_connection()


# ---------------------------------------------------------------------------
# ✅ FIX: Connection Pool داخلی — فقط برای توابع همین فایل (از طریق _db())
# ---------------------------------------------------------------------------

_POOL = None
_POOL_LOCK = threading.Lock()


def _get_pool():
    global _POOL
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                _POOL = _pg_pool.ThreadedConnectionPool(
                    minconn=1, maxconn=15, dsn=_get_database_url(), connect_timeout=15
                )
    return _POOL


@contextmanager
def _db():
    conn = _get_pool().getconn()
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("تراکنش برگشت خورد: %s", e)
        raise
    finally:
        _get_pool().putconn(conn)


# ---------------------------------------------------------------------------
# ساخت جدول‌ها + Migration
# ---------------------------------------------------------------------------

_CREATE_SQL = """
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
    feat_adx            NUMERIC(10, 4),
    feat_rsi             NUMERIC(10, 4),
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

-- جدول metadata ربات (key/value) — برای ذخیره milestone و تنظیمات بین اجراها
CREATE TABLE IF NOT EXISTS bot_meta (
    key         VARCHAR(100) PRIMARY KEY,
    value       TEXT         NOT NULL,
    updated_at  TIMESTAMPTZ  DEFAULT NOW()
);
"""

_MIGRATION_SQL = """
ALTER TABLE signals ADD COLUMN IF NOT EXISTS swing_ref          NUMERIC(20, 8);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS feat_adx           NUMERIC(10, 4);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS feat_rsi           NUMERIC(10, 4);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS feat_rsi_momentum  NUMERIC(10, 4);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS feat_ema_deviation NUMERIC(10, 4);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS feat_atr_percent   NUMERIC(10, 4);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS feat_trend_line    NUMERIC(10, 4);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS feat_body_ratio    NUMERIC(10, 4);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS rsi_score          NUMERIC(8, 2);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS adx_score          NUMERIC(8, 2);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS ema_score          NUMERIC(8, 2);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS total_score        NUMERIC(8, 2);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS ai_score           NUMERIC(8, 2);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS close_time         TIMESTAMPTZ;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS close_price        NUMERIC(20, 8);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS pnl_percent        NUMERIC(10, 4);
"""


def init_db() -> None:
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(_CREATE_SQL)
                for stmt in _MIGRATION_SQL.strip().split(';'):
                    stmt = stmt.strip()
                    if stmt:
                        cur.execute(stmt)
        logger.info("✅ init_db: جدول‌ها و migration آماده هستند.")
    except Exception as e:
        logger.critical("init_db ناموفق: %s", e)
        raise


# ---------------------------------------------------------------------------
# bot_meta — ذخیره و خواندن metadata ربات بین اجراها
# ---------------------------------------------------------------------------

def get_meta(key: str) -> str | None:
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM bot_meta WHERE key = %s", (key,))
                row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.error("get_meta خطا key=%s: %s", key, e)
        return None


def set_meta(key: str, value: str) -> bool:
    sql = """
        INSERT INTO bot_meta (key, value, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value,
                updated_at = NOW()
    """
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (key, value))
        logger.debug("set_meta: key=%s value=%s", key, value)
        return True
    except Exception as e:
        logger.error("set_meta خطا key=%s: %s", key, e)
        return False


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
    direction = kwargs.get('direction')
    if direction not in ('LONG', 'SHORT'):
        logger.warning("direction نامعتبر '%s' برای %s — ذخیره لغو شد", direction, pair)
        return None

    mapped_kwargs = kwargs.copy()
    if 'entry' in mapped_kwargs and 'entry_price' not in mapped_kwargs:
        mapped_kwargs['entry_price'] = mapped_kwargs.pop('entry')
    if 'sl' in mapped_kwargs and 'stop_loss' not in mapped_kwargs:
        mapped_kwargs['stop_loss'] = mapped_kwargs.pop('sl')

    data = {'pair': pair}
    for col in _SIGNAL_COLUMNS:
        if col != 'pair' and col in mapped_kwargs:
            data[col] = mapped_kwargs[col]

    cols         = ', '.join(data.keys())
    placeholders = ', '.join(['%s'] * len(data))
    sql          = f"INSERT INTO signals ({cols}) VALUES ({placeholders}) RETURNING id"

    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, list(data.values()))
                row    = cur.fetchone()
                new_id = row[0] if row else None
        logger.info("✅ سیگنال ذخیره شد | pair=%s direction=%s id=%s", pair, direction, new_id)
        return new_id
    except Exception as e:
        logger.error("save_signal_advanced خطا برای %s: %s", pair, e)
        return None


# ---------------------------------------------------------------------------
# پوزیشن‌های باز
# ---------------------------------------------------------------------------

def get_open_positions() -> list[dict]:
    sql = """
        SELECT id, pair AS symbol, direction,
               entry_price, stop_loss, tp1, tp2, timestamp
        FROM signals WHERE status = 'OPEN' ORDER BY timestamp ASC
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
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'")
                result = cur.fetchone()
        return int(result[0]) if result else 0
    except Exception as e:
        logger.error("get_open_positions_count خطا: %s", e)
        return 0


def get_total_closed_positions_count() -> int:
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM signals WHERE status = 'CLOSED'")
                result = cur.fetchone()
        return int(result[0]) if result else 0
    except Exception as e:
        logger.error("get_total_closed_positions_count خطا: %s", e)
        return 0


def update_position_status(signal_id: int, new_status: str,
                            pnl_percent: float, close_price: float | None = None) -> bool:
    sql = """
        UPDATE signals
        SET status = %s, pnl_percent = %s, close_price = %s, close_time = NOW()
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
        return True
    except Exception as e:
        logger.error("update_position_status خطا id=%s: %s", signal_id, e)
        return False


def get_last_signal_for_pair(pair: str) -> dict | None:
    sql = """
        SELECT direction, timestamp FROM signals
        WHERE pair = %s ORDER BY timestamp DESC LIMIT 1
    """
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (pair,))
                row = cur.fetchone()
        if not row:
            return None
        result = dict(row)
        ts = result.get('timestamp')
        if ts and isinstance(ts, datetime.datetime) and ts.tzinfo is None:
            result['timestamp'] = ts.replace(tzinfo=datetime.timezone.utc)
        return result
    except Exception as e:
        logger.error("get_last_signal_for_pair خطا %s: %s", pair, e)
        return None


def log_scan_status(pair: str, status: str, total: float = 0.0,
                    ai: float = 0.0, rsi: float = 0.0,
                    adx: float = 0.0, ema: float = 0.0) -> None:
    sql = """
        INSERT INTO scan_log (pair, status, total_score, ai_score, rsi_score, adx_score, ema_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (pair, status,
                                  round(total, 2), round(ai, 2),
                                  round(rsi, 2), round(adx, 2), round(ema, 2)))
    except Exception as e:
        logger.warning("log_scan_status خطا %s: %s", pair, e)


def get_performance_summary() -> dict:
    sql = """
        SELECT
            COUNT(*) FILTER (WHERE status = 'OPEN')                       AS open_count,
            COUNT(*) FILTER (WHERE status = 'CLOSED')                     AS closed_count,
            COUNT(*) FILTER (WHERE status='CLOSED' AND pnl_percent > 0)   AS win_count,
            ROUND(AVG(pnl_percent) FILTER (WHERE status='CLOSED'), 2)     AS avg_pnl,
            ROUND(SUM(pnl_percent) FILTER (WHERE status='CLOSED'), 2)     AS total_pnl
        FROM signals
    """
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql)
                row = cur.fetchone()
        if not row:
            return {}
        data   = dict(row)
        closed = data.get('closed_count') or 0
        wins   = data.get('win_count')    or 0
        data['win_rate'] = round(wins / closed * 100, 1) if closed > 0 else 0.0
        return data
    except Exception as e:
        logger.error("get_performance_summary خطا: %s", e)
        return {}


def get_recent_scan_logs(limit: int = 50) -> list[dict]:
    sql = """
        SELECT pair, status, total_score, ai_score, scanned_at
        FROM scan_log ORDER BY scanned_at DESC LIMIT %s
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
    where = "WHERE pair = %s"
    args  = [pair]
    if status:
        where += " AND status = %s"
        args.append(status)
    sql = f"""
        SELECT id, direction, entry_price, stop_loss, tp1, tp2,
               pnl_percent, status, timestamp, close_time, total_score, ai_score
        FROM signals {where} ORDER BY timestamp DESC LIMIT %s
    """
    args.append(limit)
    try:
        with _db() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, args)
                rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error("get_signals_for_pair خطا %s: %s", pair, e)
        return []

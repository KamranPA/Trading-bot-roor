# ---------------------------------------------------------
# FILE PATH: src/database.py (نسخه بهینه‌شده با آدرس جدید Pooler)
# ---------------------------------------------------------
import os
import psycopg2
from psycopg2.extras import DictCursor
import config

# دریافت آدرس دیتابیس از متغیر محیطی گیت‌هاب (DATABASE_URL جدید متصل به Pooler)
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    """ایجاد اتصال ایمن و پایدار به دیتابیس ابری PostgreSQL با استفاده از Connection Pooler"""
    if not DATABASE_URL:
        raise ValueError("❌ DATABASE_URL در محیط تنظیم نشده است!")
    
    url = DATABASE_URL

    # تضمین وجود پارامتر حیاتی sslmode برای امنیت اتصال به سوپابیس
    if 'sslmode' not in url:
        url += '&sslmode=require' if '?' in url else '?sslmode=require'
        
    return psycopg2.connect(url, cursor_factory=DictCursor)

def init_db(mode="live"):
    """ایجاد جداول در دیتابیس ابری (PostgreSQL)"""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # ایجاد جدول سیگنال‌ها
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id SERIAL PRIMARY KEY, 
                    timestamp TEXT, 
                    symbol TEXT, 
                    direction TEXT, 
                    entry_price REAL, 
                    stop_loss REAL, 
                    tp1 REAL, tp2 REAL,
                    status TEXT DEFAULT 'OPEN',
                    closed_at TEXT,
                    pnl_percent REAL,
                    feat_adx REAL, feat_vol_ratio REAL, feat_atr_percent REAL, 
                    feat_rsi REAL, feat_trend_line REAL, feat_ema_deviation REAL, 
                    feat_rsi_momentum REAL, feat_body_ratio REAL, feat_high_volume_session REAL
                )
            """)
            
            # ایجاد جدول لاگ‌های اسکن
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scan_logs (
                    id SERIAL PRIMARY KEY, 
                    timestamp TEXT, 
                    symbol TEXT, 
                    result TEXT,
                    total_score REAL DEFAULT 0.0,
                    ai_score REAL DEFAULT 0.0,
                    rsi_score REAL DEFAULT 0.0,
                    adx_score REAL DEFAULT 0.0,
                    ema_score REAL DEFAULT 0.0
                )
            """)
        conn.commit()

def get_open_positions():
    """دریافت لیست پوزیشن‌های باز"""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM signals WHERE status = 'OPEN'")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

def update_position_status(signal_id, status, pnl=None):
    """ثبت نتیجه نهایی معامله"""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE signals SET status = %s, pnl_percent = %s, closed_at = CURRENT_TIMESTAMP WHERE id = %s",
                (status, pnl, signal_id)
            )
        conn.commit()

def get_open_positions_count():
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'")
                return cursor.fetchone()[0]
    except: 
        return 0

def save_signal_advanced(pair, direction, entry_price, stop_loss, tp1=0, tp2=0, **kwargs):
    """ذخیره سیگنال جدید"""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, tp1, tp2) 
                   VALUES (CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s)""", 
                (pair, direction, entry_price, stop_loss, tp1, tp2)
            )
        conn.commit()

def log_scan_status(pair, status, total=0.0, ai=0.0, rsi=0.0, adx=0.0, ema=0.0):
    """ذخیره امتیازهای اسکن"""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO scan_logs 
                   (timestamp, symbol, result, total_score, ai_score, rsi_score, adx_score, ema_score) 
                   VALUES (CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s, %s)""", 
                (pair, status, total, ai, rsi, adx, ema)
            )
        conn.commit()

def manage_open_positions():
    pass

# ---------------------------------------------------------
# FILE PATH: src/database.py (نسخه بهینه‌شده با آدرس جدید Pooler - هماهنگ با ML و مدیریت ریسک)
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
            # ایجاد جدول سیگنال‌ها (پشتیبانی از position_size اضافه شد)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id SERIAL PRIMARY KEY, 
                    timestamp TEXT, 
                    symbol TEXT, 
                    direction TEXT, 
                    entry_price REAL, 
                    stop_loss REAL, 
                    tp1 REAL, tp2 REAL,
                    position_size REAL DEFAULT 0.0,
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
    """ذخیره سیگنال جدید در دیتابیس همراه با سنسورهای ماشین لرنینگ (بدون ارسال تکراری به تلگرام)"""
    # استخراج امن مقادیر سنسورها از kwargs (اگر موجود نبودند مقدار پیش‌فرض جایگزین می‌شود)
    position_size = kwargs.get('position_size', 0.0)
    feat_adx = kwargs.get('feat_adx', 0.0)
    feat_vol_ratio = kwargs.get('feat_vol_ratio', 1.0)
    feat_atr_percent = kwargs.get('feat_atr_percent', 0.0)
    feat_rsi = kwargs.get('feat_rsi', 50.0)
    feat_trend_line = kwargs.get('feat_trend_line', 0.0)
    feat_ema_deviation = kwargs.get('feat_ema_deviation', 0.0)
    feat_rsi_momentum = kwargs.get('feat_rsi_momentum', 0.0)
    feat_body_ratio = kwargs.get('feat_body_ratio', 0.0)
    feat_high_volume_session = kwargs.get('feat_high_volume_session', 0.0)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO signals 
                   (timestamp, symbol, direction, entry_price, stop_loss, tp1, tp2, position_size,
                    feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line, 
                    feat_ema_deviation, feat_rsi_momentum, feat_body_ratio, feat_high_volume_session) 
                   VALUES (CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", 
                (pair, direction, entry_price, stop_loss, tp1, tp2, position_size,
                 feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line,
                 feat_ema_deviation, feat_rsi_momentum, feat_body_ratio, feat_high_volume_session)
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

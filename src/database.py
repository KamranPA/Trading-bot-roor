# ---------------------------------------------------------
# FILE PATH: src/database.py (نسخه نهایی و ۱۰۰٪ سازگار با GitHub Actions)
# ---------------------------------------------------------
import os
import socket
import psycopg2
from psycopg2.extras import DictCursor
import config

# دریافت آدرس دیتابیس از متغیر محیطی گیت‌هاب
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    """ایجاد اتصال ایمن به دیتابیس ابری PostgreSQL با دور زدن مشکلات شبکه و IPv6"""
    global DATABASE_URL
    if not DATABASE_URL:
        raise ValueError("❌ DATABASE_URL در محیط تنظیم نشده است!")
    
    url = DATABASE_URL
    
    # 🛠️ اصلاح ۱: استخراج هاست و تبدیل اجباری آن به IPv4 برای حل مشکل شبکه گیت‌هاب
    try:
        parts = url.split('@')
        if len(parts) > 1:
            host_port_db = parts[1]
            host = host_port_db.split(':')[0]
            ipv4_address = socket.gethostbyname(host)
            url = url.replace(host, ipv4_address)
    except Exception as e:
        print(f"⚠️ هشدار در تبدیل DNS به IPv4: {e}")

    # 🛠️ اصلاح ۲: تضمین وجود پورت ۶۵۴۳ به جای ۵۴۳۲ برای GitHub Actions
    if ":5432" in url:
        url = url.replace(":5432", ":6543")

    # 🛠️ اصلاح ۳: اضافه کردن پارامتر حیاتی sslmode
    if 'sslmode' not in url:
        url += '&sslmode=require' if '?' in url else '?sslmode=require'
        
    return psycopg2.connect(url, cursor_factory=DictCursor)

def init_db(mode="live"):
    """ایجاد جداول در دیتابیس ابری (PostgreSQL)"""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # PostgreSQL از SERIAL برای افزایش خودکار ID استفاده می‌کند
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
            # تبدیل به دیکشنری جهت سازگاری با کدهای موجود شما
            return [dict(row) for row in rows]

def update_position_status(signal_id, status, pnl=None):
    """ثبت نتیجه نهایی معامله"""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # استفاده از %s استاندارد PostgreSQL
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

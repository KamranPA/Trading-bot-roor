# ---------------------------------------------------------
# FILE PATH: src/database.py (نسخه معماری دوگانه - Supabase برای لایو/ماهانه، SQLite برای بک‌تست)
# ---------------------------------------------------------
import os
import psycopg2
from psycopg2.extras import DictCursor
import sqlite3
import config

# دریافت آدرس دیتابیس ابری
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection(mode="live"):
    """
    سویچ هوشمند دیتابیس: 
    - در حالت backtest از دیتابیس محلی گیت‌هاب (SQLite) استفاده می‌کند.
    - در حالت لایو یا ماهانه از سوپابیس (PostgreSQL) استفاده می‌کند.
    """
    if mode == "backtest":
        # اتصال به دیتابیس محلی گیت‌هاب برای بک‌تست
        os.makedirs(os.path.dirname(config.DB_PATH_BACKTEST), exist_ok=True)
        # در SQLite، row_factory را تنظیم می‌کنیم تا خروجی شبیه DictCursor شود
        conn = sqlite3.connect(config.DB_PATH_BACKTEST)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"
    else:
        # اتصال به دیتابیس ابری سوپابیس برای اجرای لایو و آموزش ماهانه
        if not DATABASE_URL:
            raise ValueError("❌ DATABASE_URL در محیط تنظیم نشده است!")
        
        url = DATABASE_URL
        if 'sslmode' not in url:
            url += '&sslmode=require' if '?' in url else '?sslmode=require'
            
        return psycopg2.connect(url, cursor_factory=DictCursor), "postgres"

def init_db(mode="live"):
    """ایجاد جداول متناسب با نوع دیتابیس (PostgreSQL یا SQLite)"""
    conn, db_type = get_connection(mode)
    
    # تنظیم کوئری‌ها بر اساس نوع دیتابیس (SQLite از SERIAL پشتیبانی نمی‌کند)
    id_type = "SERIAL PRIMARY KEY" if db_type == "postgres" else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    with conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS signals (
                id {id_type}, 
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
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS scan_logs (
                id {id_type}, 
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
    if db_type == "postgres":
        conn.close() # بستن دستی کانکشن‌های سایکوپیجی

def get_open_positions(mode="live"):
    """دریافت لیست پوزیشن‌های باز"""
    conn, db_type = get_connection(mode)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM signals WHERE status = 'OPEN'")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    finally:
        if db_type == "postgres": conn.close()

def update_position_status(signal_id, status, pnl=None, mode="live"):
    """ثبت نتیجه نهایی معامله"""
    conn, db_type = get_connection(mode)
    try:
        # سینتکس پارامترها در سایکوپیجی %s و در اس‌کیوال‌لایت ? است
        param_placeholder = "%s" if db_type == "postgres" else "?"
        
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE signals SET status = {param_placeholder}, pnl_percent = {param_placeholder}, closed_at = CURRENT_TIMESTAMP WHERE id = {param_placeholder}",
                (status, pnl, signal_id)
            )
    finally:
        if db_type == "postgres": conn.close()

def get_open_positions_count(mode="live"):
    try:
        conn, db_type = get_connection(mode)
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'")
            return cursor.fetchone()[0]
    except: 
        return 0
    finally:
        if 'db_type' in locals() and db_type == "postgres": conn.close()

def save_signal_advanced(pair, direction, entry_price, stop_loss, tp1=0, tp2=0, mode="live", **kwargs):
    """ذخیره سیگنال جدید در دیتابیس همراه با سنسورهای ماشین لرنینگ"""
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

    conn, db_type = get_connection(mode)
    param_placeholder = "%s" if db_type == "postgres" else "?"
    placeholders = ", ".join([param_placeholder] * 16) # 16 متغیر برای ذخیره

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""INSERT INTO signals 
                   (timestamp, symbol, direction, entry_price, stop_loss, tp1, tp2, position_size,
                    feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line, 
                    feat_ema_deviation, feat_rsi_momentum, feat_body_ratio, feat_high_volume_session) 
                   VALUES (CURRENT_TIMESTAMP, {placeholders})""", 
                (pair, direction, entry_price, stop_loss, tp1, tp2, position_size,
                 feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line,
                 feat_ema_deviation, feat_rsi_momentum, feat_body_ratio, feat_high_volume_session)
            )
    finally:
        if db_type == "postgres": conn.close()

def log_scan_status(pair, status, total=0.0, ai=0.0, rsi=0.0, adx=0.0, ema=0.0, mode="live"):
    """ذخیره امتیازهای اسکن"""
    conn, db_type = get_connection(mode)
    param_placeholder = "%s" if db_type == "postgres" else "?"
    placeholders = ", ".join([param_placeholder] * 7)

    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""INSERT INTO scan_logs 
                   (timestamp, symbol, result, total_score, ai_score, rsi_score, adx_score, ema_score) 
                   VALUES (CURRENT_TIMESTAMP, {placeholders})""", 
                (pair, status, total, ai, rsi, adx, ema)
            )
    finally:
        if db_type == "postgres": conn.close()

def manage_open_positions():
    pass

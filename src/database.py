# ---------------------------------------------------------
# FILE NAME: src/database.py
# ---------------------------------------------------------
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

def init_db():
    """🛡️ راه‌اندازی و به‌روزرسانیِ فوق‌هوشمند دیتابیس"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # ۱. اطمینان از وجود جدول اصلی
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                status TEXT DEFAULT 'OPEN'
            )
        """)
        
        # ۲. مهاجرت ستون‌ها (Migration) - چک کردنِ ستون‌های حیاتی
        cursor.execute("PRAGMA table_info(signals)")
        existing_cols = [row[1] for row in cursor.fetchall()]
        
        required_cols = {
            "stop_loss": "REAL",
            "status": "TEXT DEFAULT 'OPEN'",
            "pnl_percent": "REAL DEFAULT 0.0",
            "feat_adx": "REAL"
        }
        
        for col, col_type in required_cols.items():
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE signals ADD COLUMN {col} {col_type}")
                print(f"✅ ستون {col} با موفقیت به دیتابیس اضافه شد.")

        # ۳. ایجاد سایر جداول
        cursor.execute("CREATE TABLE IF NOT EXISTS signal_targets (id INTEGER PRIMARY KEY, signal_id INTEGER, target_number INTEGER, target_price REAL, status TEXT DEFAULT 'PENDING')")
        cursor.execute("CREATE TABLE IF NOT EXISTS scan_logs (id INTEGER PRIMARY KEY, timestamp TEXT, symbol TEXT, result TEXT)")

def manage_open_positions(conn):
    """مدیریت پوزیشن‌های باز"""
    try:
        cursor = conn.cursor()
        # استفاده از دستور امن برای جلوگیری از خطا
        cursor.execute("SELECT id, symbol, entry_price, stop_loss FROM signals WHERE status = 'OPEN'")
        return cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"❌ خطای عملیاتی دیتابیس: {e}")
        return []

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, **features):
    """ثبت سیگنال با بررسی ساختار ستون‌ها"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            query = "INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, status) VALUES (?, ?, ?, ?, ?, ?)"
            cursor.execute(query, (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), symbol, direction, entry_price, stop_loss, "OPEN"))
            conn.commit()
    except Exception as e:
        print(f"❌ خطا در ثبت سیگنال: {e}")

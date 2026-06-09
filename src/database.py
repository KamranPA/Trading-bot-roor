# FILE PATH: /src/database.py
import sqlite3
import os

# تعیین مسیر دقیق (فایل دیتابیس همیشه در پوشه data در روت پروژه است)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_NAME = os.path.join(DATA_DIR, "trading_bot.db")

def init_db():
    """تضمین سلامت دیتابیس و جدول بدون آسیب به داده‌های قبلی"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                stop_loss REAL,
                tp1 REAL,
                tp2 REAL,
                status TEXT
            )
        """)
        conn.commit()

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2):
    """ذخیره سیگنال (این همان تابعی است که در main.py استفاده می‌کنید)"""
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, tp1, tp2, status)
            VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, 'OPEN')
        """, (symbol, direction, entry_price, stop_loss, tp1, tp2))
        conn.commit()

def manage_open_positions():
    """خوانش پوزیشن‌های باز (بدون نیاز به آرگومان ورودی)"""
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute("SELECT id, symbol, entry_price, stop_loss FROM signals WHERE status = 'OPEN'").fetchall()

def get_open_positions_count():
    """شمارش پوزیشن‌ها"""
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]

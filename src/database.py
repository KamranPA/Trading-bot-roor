import sqlite3
import os

DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trading_bot.db")

def init_db():
    """راه‌اندازی و تعمیر خودکار ساختار دیتابیس"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # ایجاد جدول در صورت نبودن
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                stop_loss REAL,
                status TEXT DEFAULT 'OPEN'
            )
        """)
        
        # بررسی و اضافه کردن ستون‌های گمشده (رفع خطای no such column)
        cursor.execute("PRAGMA table_info(signals)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'stop_loss' not in columns:
            cursor.execute("ALTER TABLE signals ADD COLUMN stop_loss REAL")
        if 'status' not in columns:
            cursor.execute("ALTER TABLE signals ADD COLUMN status TEXT DEFAULT 'OPEN'")
        conn.commit()

def manage_open_positions():
    """واکشی پوزیشن‌های باز بدون نیاز به ورودی conn"""
    init_db() # اطمینان از سلامت دیتابیس قبل از خواندن
    with sqlite3.connect(DB_NAME) as conn:
        try:
            return conn.execute("SELECT id, symbol, entry_price, stop_loss FROM signals WHERE status = 'OPEN'").fetchall()
        except sqlite3.OperationalError:
            return []

def get_open_positions_count():
    """شمارش پوزیشن‌های باز"""
    with sqlite3.connect(DB_NAME) as conn:
        try:
            result = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()
            return result[0] if result else 0
        except:
            return 0

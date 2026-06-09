# FILE PATH: /src/database.py
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

def init_db():
    if not os.path.exists(os.path.dirname(DB_NAME)):
        os.makedirs(os.path.dirname(DB_NAME))
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                stop_loss REAL,
                tp1 REAL,
                tp2 REAL,
                status TEXT DEFAULT 'OPEN'
            )
        """)
        conn.commit()

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2):
    """ذخیره سیگنال با ثبت قطعی در دیتابیس"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, tp1, tp2, status)
            VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, 'OPEN')
        """, (symbol, direction, entry_price, stop_loss, tp1, tp2))
        conn.commit() # ثبت نهایی برای جلوگیری از گم شدن داده‌ها

def manage_open_positions():
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute("SELECT id, symbol, entry_price, stop_loss FROM signals WHERE status = 'OPEN'").fetchall()

def get_open_positions_count():
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]

import sqlite3
import os

DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trading_bot.db")

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY, timestamp TEXT, symbol TEXT, 
                direction TEXT, entry_price REAL, stop_loss REAL, status TEXT DEFAULT 'OPEN'
            )
        """)
        # اضافه کردن ستون stop_loss اگر وجود ندارد
        cursor.execute("PRAGMA table_info(signals)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'stop_loss' not in cols:
            cursor.execute("ALTER TABLE signals ADD COLUMN stop_loss REAL")
        conn.commit()

def manage_open_positions(conn):
    return conn.execute("SELECT id, symbol, entry_price, stop_loss FROM signals WHERE status = 'OPEN'").fetchall()

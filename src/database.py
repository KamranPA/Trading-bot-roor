import sqlite3
import os
from datetime import datetime

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
        conn.commit()

def manage_open_positions(conn):
    return conn.execute("SELECT id, symbol, entry_price, stop_loss FROM signals WHERE status = 'OPEN'").fetchall()

def get_open_positions_count(conn):
    return conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]

def save_signal_advanced(symbol, direction, entry_price, stop_loss, **kwargs):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, status) VALUES (?, ?, ?, ?, ?, ?)", 
                     (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), symbol, direction, entry_price, stop_loss, "OPEN"))
        conn.commit()

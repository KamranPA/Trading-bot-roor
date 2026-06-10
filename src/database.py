import sqlite3
import os
import config

# مسیر ثابت دیتابیس در پوشه data
DB_PATH = os.path.join("data", config.DB_NAME)

def init_db():
    if not os.path.exists("data"):
        os.makedirs("data")
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, symbol TEXT, direction TEXT, entry_price REAL, stop_loss REAL, status TEXT DEFAULT 'OPEN')")
        cursor.execute("CREATE TABLE IF NOT EXISTS scan_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, symbol TEXT, result TEXT)")
        conn.commit()

def get_open_positions_count():
    try:
        if not os.path.exists(DB_PATH): return 0
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]
    except: return 0

def save_signal_advanced(pair, direction, entry_price, stop_loss, **kwargs):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss) VALUES (datetime('now'), ?, ?, ?, ?)", 
                     (pair, direction, entry_price, stop_loss))
        conn.commit()

def log_scan_status(pair, status):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO scan_logs (timestamp, symbol, result) VALUES (datetime('now'), ?, ?)", (pair, status))
        conn.commit()

def manage_open_positions():
    if not os.path.exists(DB_PATH): return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE signals SET status = 'CLOSED' WHERE status = 'OPEN'")
        conn.commit()

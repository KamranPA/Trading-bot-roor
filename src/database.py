import sqlite3
import config
import os

# استفاده از مسیر ساده در ریشه پروژه
DB_PATH = config.DB_NAME

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, symbol TEXT, direction TEXT, 
            entry_price REAL, stop_loss REAL, status TEXT DEFAULT 'OPEN'
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS scan_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, symbol TEXT, result TEXT)")
    conn.commit()
    conn.close()

# این تابع همان چیزی است که main.py شما صدا می‌زند
def get_open_positions_count():
    try:
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]
        conn.close()
        return count
    except:
        return 0

# سایر توابع شما که در main.py استفاده شده‌اند
def save_signal_advanced(pair, direction, entry_price, stop_loss, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss) VALUES (datetime('now'), ?, ?, ?, ?)", 
                 (pair, direction, entry_price, stop_loss))
    conn.commit()
    conn.close()

def log_scan_status(pair, status):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO scan_logs (timestamp, symbol, result) VALUES (datetime('now'), ?, ?)", (pair, status))
    conn.commit()
    conn.close()

def manage_open_positions():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE signals SET status = 'CLOSED' WHERE status = 'OPEN'") # منطق بستن پوزیشن
    conn.commit()
    conn.close()

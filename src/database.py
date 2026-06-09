import sqlite3
import os

# مسیر مطلق برای اینکه در گوشی یا سرور گم نشود
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trading_bot.db")

def _get_connection():
    # تضمین وجود پوشه data
    if not os.path.exists(os.path.dirname(DB_PATH)):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    """ساخت اجباری جدول در هر بار فراخوانی"""
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    conn.close()

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2):
    init_db() # ساخت اجباری قبل از درج
    conn = _get_connection()
    conn.execute("""
        INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, tp1, tp2, status)
        VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, 'OPEN')
    """, (symbol, direction, entry_price, stop_loss, tp1, tp2))
    conn.commit()
    conn.close()

def manage_open_positions():
    init_db() # ساخت اجباری قبل از خواندن
    conn = _get_connection()
    data = conn.execute("SELECT id, symbol, entry_price, stop_loss FROM signals WHERE status = 'OPEN'").fetchall()
    conn.close()
    return data

def get_open_positions_count():
    init_db() # ساخت اجباری قبل از شمارش
    conn = _get_connection()
    count = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]
    conn.close()
    return count

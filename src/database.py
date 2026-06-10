import sqlite3
import os
import config

# مسیر دیتابیس دقیقاً در پوشه data/ قرار می‌گیرد
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, config.DB_NAME)

def init_db():
    """مقداردهی اولیه: اطمینان از وجود پوشه دیتا و جداول"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, 
                symbol TEXT, 
                direction TEXT, 
                entry_price REAL, 
                stop_loss REAL, 
                status TEXT DEFAULT 'OPEN'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, 
                symbol TEXT, 
                result TEXT
            )
        """)
        conn.commit()

def get_open_positions_count():
    """برگرداندن تعداد پوزیشن‌های باز (جلوگیری از خطا در صورت نبود دیتابیس)"""
    try:
        if not os.path.exists(DB_PATH):
            return 0
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]
    except Exception:
        return 0

def save_signal_advanced(pair, direction, entry_price, stop_loss, **kwargs):
    """ذخیره سیگنال جدید"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss) 
            VALUES (datetime('now'), ?, ?, ?, ?)
        """, (pair, direction, entry_price, stop_loss))
        conn.commit()

def log_scan_status(pair, status):
    """ثبت لاگ اسکن"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO scan_logs (timestamp, symbol, result) VALUES (datetime('now'), ?, ?)", (pair, status))
        conn.commit()

def manage_open_positions():
    """بستن پوزیشن‌های باز"""
    if not os.path.exists(DB_PATH):
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE signals SET status = 'CLOSED' WHERE status = 'OPEN'")
        conn.commit()

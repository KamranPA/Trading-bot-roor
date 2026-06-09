import sqlite3
import os

# مسیر مطلق برای جلوگیری از گم شدن فایل در سرور
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

def init_db():
    if not os.path.exists(os.path.dirname(DB_NAME)):
        os.makedirs(os.path.dirname(DB_NAME))
    
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # ساخت جدول پایه
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
        # اصلاح ستون‌ها اگر قبلاً ساخته شده ولی ناقص هستند
        cursor.execute("PRAGMA table_info(signals)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'stop_loss' not in cols:
            cursor.execute("ALTER TABLE signals ADD COLUMN stop_loss REAL")
        conn.commit()

# توابعی که main.py شما به آن‌ها نیاز دارد
def manage_open_positions():
    init_db() # تضمین سلامت دیتابیس قبل از خواندن
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute("SELECT id, symbol, entry_price, stop_loss FROM signals WHERE status = 'OPEN'").fetchall()

def get_open_positions_count():
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        return conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]

import sqlite3
import os
import logging
import datetime

# تنظیم مسیر دیتابیس
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(DATA_DIR): 
    os.makedirs(DATA_DIR)
DB_PATH = os.path.join(DATA_DIR, "trading_bot.db")

def init_db():
    """مقداردهی اولیه و ایجاد جداول (با لحاظ ستون‌های امتیاز)"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # ایجاد جدول سیگنال‌ها
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, 
                pair TEXT, 
                direction TEXT, 
                entry_price REAL, 
                sl REAL, 
                tp1 REAL, 
                tp2 REAL, 
                status TEXT, 
                pnl REAL DEFAULT 0, 
                position_size REAL, 
                signal_score REAL DEFAULT 0.0
            )
        """)
        
        # ایجاد جدول لاگ‌های اسکن
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, 
                symbol TEXT, 
                result TEXT, 
                signal_score REAL DEFAULT 0.0
            )
        """)
        
        # آپدیت امن برای اضافه کردن ستون در صورت نبودن
        try: 
            cursor.execute("ALTER TABLE scan_logs ADD COLUMN signal_score REAL DEFAULT 0.0")
        except sqlite3.OperationalError: 
            pass
        
        conn.commit()

def log_scan_status(symbol, status, signal_score=0.0):
    """ثبت لاگ اسکن با ۳ ورودی الزامی"""
    try:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(DB_PATH, timeout=15) as conn:
            conn.execute("""
                INSERT INTO scan_logs (timestamp, symbol, result, signal_score) 
                VALUES (?, ?, ?, ?)
            """, (timestamp, symbol, status, float(signal_score)))
            conn.commit()
    except Exception as e: 
        logging.error(f"DB Error in log_scan_status: {e}")

def get_open_positions_count():
    """شمارش پوزیشن‌های باز"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            return conn.execute("SELECT count(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]
    except Exception as e: 
        logging.error(f"Error in get_open_positions_count: {e}")
        return 0

def save_signal_advanced(pair, direction, entry_price, sl, tp1, tp2, position_size, signal_score=0.0, **kwargs):
    """ذخیره سیگنال جدید با امتیاز"""
    try:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(DB_PATH, timeout=15) as conn:
            conn.execute("""
                INSERT INTO signals (timestamp, pair, direction, entry_price, sl, tp1, tp2, status, position_size, signal_score) 
                VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
            """, (timestamp, pair, direction, entry_price, sl, tp1, tp2, position_size, float(signal_score)))
            conn.commit()
    except Exception as e: 
        logging.error(f"Save Signal Error: {e}")

def update_position_status(sig_id, status, pnl=0.0):
    """به‌روزرسانی وضعیت پوزیشن"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            conn.execute("UPDATE signals SET status = ?, pnl = ? WHERE id = ?", (status, pnl, sig_id))
            conn.commit()
    except Exception as e: 
        logging.error(f"Error in update_position_status: {e}")

def get_open_positions():
    """دریافت لیست پوزیشن‌های باز"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            return conn.execute("SELECT * FROM signals WHERE status = 'OPEN'").fetchall()
    except Exception as e: 
        logging.error(f"Error in get_open_positions: {e}")
        return []

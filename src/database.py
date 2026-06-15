# ---------------------------------------------------------
# FILE PATH: src/database.py (اصلاح شده: مدیریت هوشمند پوزیشن‌ها)
# ---------------------------------------------------------
import sqlite3
import os
import logging
import datetime

# مسیر فایل دیتابیس - اطمینان حاصل کنید پوشه data وجود دارد
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
DB_PATH = os.path.join(DATA_DIR, "trading_bot.db")

def init_db():
    """مقداردهی اولیه و ایجاد جداول مورد نیاز در دیتابیس"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # جدول سیگنال‌های فعال (پوزیشن‌ها)
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
        
        # جدول لاگ‌های اسکن (با ستون امتیاز)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                result TEXT,
                signal_score REAL DEFAULT 0.0
            )
        """)
        
        # آپدیت امن دیتابیس‌های قدیمی (در صورت وجود ستون امتیاز اضافه می‌شود)
        try:
            cursor.execute("ALTER TABLE scan_logs ADD COLUMN signal_score REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            pass # ستون قبلاً وجود دارد
            
        conn.commit()

def log_scan_status(symbol, status, signal_score=0.0):
    """ثبت لاگ اسکن به همراه امتیاز در دیتابیس (ارتقا یافته برای دریافت ۳ ورودی)"""
    try:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(DB_PATH, timeout=15) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scan_logs (timestamp, symbol, result, signal_score) 
                VALUES (?, ?, ?, ?)
            """, (timestamp, symbol, status, signal_score))
            conn.commit()
    except Exception as e:
        logging.error(f"خطا در ثبت لاگ در دیتابیس: {e}")

def save_signal_advanced(pair, direction, entry_price, sl, tp1, tp2, position_size, signal_score=0.0, **kwargs):
    """ذخیره سیگنال جدید در دیتابیس"""
    try:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(DB_PATH, timeout=15) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO signals (timestamp, pair, direction, entry_price, sl, tp1, tp2, status, position_size, signal_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
            """, (timestamp, pair, direction, entry_price, sl, tp1, tp2, position_size, signal_score))
            conn.commit()
    except Exception as e:
        logging.error(f"خطا در ذخیره سیگنال: {e}")

def get_open_positions():
    """دریافت پوزیشن‌های باز برای بررسی حد سود و ضرر"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            return conn.execute("SELECT * FROM signals WHERE status = 'OPEN'").fetchall()
    except Exception as e:
        logging.error(f"خطا در خواندن پوزیشن‌های باز: {e}")
        return []

def update_position_status(sig_id, status, pnl=0.0):
    """به‌روزرسانی وضعیت پوزیشن"""
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            conn.execute("UPDATE signals SET status = ?, pnl = ? WHERE id = ?", (status, pnl, sig_id))
            conn.commit()
    except Exception as e:
        logging.error(f"خطا در آپدیت وضعیت پوزیشن: {e}")

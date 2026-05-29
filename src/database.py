# src/database.py
# ماژول مدیریت دیتابیس (ذخیره، بازخوانی و به‌روزرسانی سیگنال‌ها)

import sqlite3
import os

# تعیین مسیر فایل دیتابیس در پوشه data
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trading_bot.db")

def get_connection():
    """ایجاد اتصال به فایل دیتابیس و اطمینان از فعال بودن کلیدهای خارجی"""
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    """ساخت فایل دیتابیس و جدول سیگنال‌ها در صورتی که از قبل وجود نداشته باشند"""
    # ایجاد پوشه data در صورتی که وجود نداشته باشد
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            tp1 REAL NOT NULL,
            tp2 REAL NOT NULL,
            atr_value REAL NOT NULL,
            adx_value REAL NOT NULL,
            status TEXT DEFAULT 'OPEN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_signal(signal_data):
    """ذخیره یک سیگنال جدید در دیتابیس"""
    if signal_data is None:
        return False
        
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO signals (pair, direction, entry_price, stop_loss, tp1, tp2, atr_value, adx_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal_data['pair'],
            signal_data['direction'],
            signal_data['entry_price'],
            signal_data['stop_loss'],
            signal_data['tp1'],
            signal_data['tp2'],
            signal_data['atr_value'],
            signal_data['adx_value']
        ))
        conn.commit()
        return True
    except Exception as e:
        print(f"خطا در ذخیره سیگنال در دیتابیس: {e}")
        return False
    finally:
        conn.close()

def get_open_signals():
    """دریافت تمام سیگنال‌هایی که هنوز وضعیت آن‌ها باز (OPEN یا TP1_HIT) است"""
    conn = get_connection()
    # تغییر فرمت خروجی به دیکشنری برای خوانایی بهتر در کدهای دیگر
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # پوزیشن‌هایی که وضعیتشان OPEN یا TP1_HIT است نیاز به مانیتورینگ دارند
    cursor.execute("SELECT * FROM signals WHERE status IN ('OPEN', 'TP1_HIT')")
    rows = cursor.fetchall()
    
    # تبدیل خروجی دیتابیس به فرمت لیست و دیکشنری پایتون
    open_signals = [dict(row) for row in rows]
    conn.close()
    return open_signals

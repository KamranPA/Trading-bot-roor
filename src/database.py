import sqlite3
from datetime import datetime

DB_NAME = "trading_bot.db"

def init_db():
    """ایجاد دیتابیس و جدول‌های مورد نیاز در صورت عدم وجود"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # جدول ثبت سیگنال‌ها
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            status TEXT
        )
    ''')
    
    # جدول ثبت وضعیت اسکن‌ها برای خود‌ارتقایی
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            result TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def log_scan(symbol, result):
    """ثبت وضعیت هر اسکن در دیتابیس"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scan_logs (timestamp, symbol, result) VALUES (?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, result)
    )
    conn.commit()
    conn.close()

def check_filters_lock():
    """
    بررسی هوشمند دیتابیس: اگر اسکن‌های متوالی طولانی هیچ سیگنالی تولید نکنند،
    سیستم متوجه قفل شدن فیلترها می‌شود.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT result FROM scan_logs ORDER BY id DESC LIMIT 180")
    logs = cursor.fetchall()
    conn.close()
    
    if len(logs) >= 180 and all(log[0] == "No Signal" for log in logs):
        print("⚠️ سیستم متوجه قفل شدن فیلترها شد! نیاز به بهینه‌سازی میکروسکوپی.")
        return True
    return False

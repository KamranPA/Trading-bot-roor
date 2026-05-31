import os
import sqlite3
from datetime import datetime

# پیدا کردن مسیر ریشه پروژه (یک پوشه عقب‌تر از پوشه src)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# آدرس‌دهی دقیق و داینامیک به فایل دیتابیس درون پوشه data
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

def init_db():
    """ایجاد دیتابیس و جدول‌های مورد نیاز در پوشه data در صورت عدم وجود"""
    # مطمئن شدن از اینکه پوشه data وجود دارد (اگر نبود ساخته می‌شود)
    data_dir = os.path.dirname(DB_NAME)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # ۱. جدول ثبت سیگنال‌ها (جهت، قیمت ورود و وضعیت پوزیشن)
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
    
    # ۲. جدول ثبت وضعیت تمام اسکن‌ها برای فرآیند خود‌ارتقایی (Self-Correction)
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
    """ثبت وضعیت و خروجی هر اسکن در دیتابیس جهت تحلیل‌های آینده ربات"""
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
    بررسی هوشمند دیتابیس برای فرآیند یادگیری ماشین (brain.py):
    اگر ۱۸۰ اسکن متوالی (حدود یک ماه در اسکن‌های زمان‌بندی شده) هیچ سیگنالی تولید نکنند،
    سیستم متوجه بن‌بست فیلترها شده و این موضوع را گزارش می‌دهد.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # خواندن وضعیت ۱۸۰ اسکن آخر از دیتابیس
        cursor.execute("SELECT result FROM scan_logs ORDER BY id DESC LIMIT 180")
        logs = cursor.fetchall()
    except sqlite3.OperationalError:
        # اگر جدول هنوز ساخته نشده باشد
        logs = []
    finally:
        conn.close()
    
    # اگر ۱۸۰ اسکن انجام شده بود و همگی "No Signal" بودند
    if len(logs) >= 180 and all(log[0] == "No Signal" for log in logs):
        print("⚠️ [Brain Setup]: سیستم متوجه قفل شدن فیلترها شد! ماژول خود‌ارتقایی فعال می‌شود.")
        return True
        
    return False

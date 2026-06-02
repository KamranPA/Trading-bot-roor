# src/database.py
# ماژول مدیریت دیتابیس (نسخه v1.3 - مجهز به فیوز جلوگیری از سیگنال تکراری)

import os
import sqlite3
from datetime import datetime

# پیدا کردن مسیر ریشه پروژه (یک پوشه عقب‌تر از پوشه src)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# آدرس‌دهی دقیق و داینامیک به فایل دیتابیس درون پوشه data
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

def init_db():
    """ایجاد دیتابیس و جدول‌های مورد نیاز در پوشه data در صورت عدم وجود"""
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
    اگر ۱۸۰ اسکن متوالی هیچ سیگنالی تولید نکنند،
    سیستم متوجه بن‌بست فیلترها شده و این موضوع را گزارش می‌دهد.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT result FROM scan_logs ORDER BY id DESC LIMIT 180")
        logs = cursor.fetchall()
    except sqlite3.OperationalError:
        logs = []
    finally:
        conn.close()
    
    if len(logs) >= 180 and all(log[0] == "No Signal" for log in logs):
        print("⚠️ [Brain Setup]: سیستم متوجه قفل شدن فیلترها شد! ماژول خود‌ارتقایی فعال می‌شود.")
        return True
        
    return False

# =====================================================================
# 🛡️ بخش جدید: توابع کنترل و مدیریت فیوز امنیتی پوزیشن‌های باز
# =====================================================================

def has_open_position(symbol):
    """
    بررسی اینکه آیا پوزیشن باز و مدیریت‌نشده (وضعیت 'OPEN') برای این ارز در دیتابیس وجود دارد یا خیر
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    query = "SELECT 1 FROM signals WHERE symbol = ? AND status = 'OPEN' LIMIT 1;"
    
    try:
        cursor.execute(query, (symbol,))
        result = cursor.fetchone()
        return result is not None
    except sqlite3.OperationalError:
        # در صورتی که جدول هنوز ساخته نشده باشد یا مشکلی در خواندن باشد
        return False
    finally:
        conn.close()

def save_signal(symbol, direction, entry_price, status="OPEN"):
    """
    ثبت سیگنال جدید در دیتابیس با وضعیت اولیه OPEN برای فعال شدن فیوز امنیتی
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    query = """
        INSERT INTO signals (timestamp, symbol, direction, entry_price, status)
        VALUES (?, ?, ?, ?, ?)
    """
    
    cursor.execute(
        query, 
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, direction, entry_price, status)
    )
    conn.commit()
    conn.close()

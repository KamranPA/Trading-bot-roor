# src/database.py
# ماژول جامع و ساختاریافته مدیریت دیتابیس (نسخه v2.0 - نسخه طلایی)

import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

def init_db():
    """راه‌اندازی ساختار کامل و مدرن دیتابیس به همراه مکانیزم مهاجرت خودکار ستون‌ها"""
    data_dir = os.path.dirname(DB_NAME)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # ۱. ایجاد جدول جامع سیگنال‌ها و پوزیشن‌ها با جزئیات کامل خروج و مدیریت ریسک
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            tp1 REAL,
            tp2 REAL,
            stop_loss REAL,
            exit_price REAL,
            status TEXT,
            closed_at TEXT,
            pnl_percent REAL
        )
    ''')
    
    # ۲. ایجاد جدول جعبه سیاه (لاگ اسکن‌ها برای تغذیه Brain)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            result TEXT
        )
    ''')
    
    # 🛡️ سیستم هوشمند آپدیت خودکار دیتابیس (اگر ستون‌ها در دیتابیس گیت‌هاب موجود نباشند اضافه می‌شوند)
    ستون_های_جدید = {
        "tp1": "REAL",
        "tp2": "REAL",
        "stop_loss": "REAL",
        "exit_price": "REAL",
        "closed_at": "TEXT",
        "pnl_percent": "REAL"
    }
    
    for column, col_type in ستون_های_جدید.items():
        try:
            cursor.execute(f"ALTER TABLE signals ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError:
            # ستون از قبل وجود دارد، عملیات رد می‌شود
            pass
            
    conn.commit()
    conn.close()

def log_scan(symbol, result):
    """ثبت لاگ ریز به ریز اسکن‌ها برای مانیتورینگ عملکرد استراتژی"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scan_logs (timestamp, symbol, result) VALUES (?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, result)
    )
    conn.commit()
    conn.close()

def save_signal(symbol, direction, entry_price, tp1, tp2, stop_loss, status="OPEN"):
    """قفل کردن پوزیشن جدید با تمام پارامترهای مدیریت ریسک و تارگت‌ها"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    query = """
        INSERT INTO signals (timestamp, symbol, direction, entry_price, tp1, tp2, stop_loss, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    try:
        cursor.execute(
            query, 
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), symbol, direction, entry_price, tp1, tp2, stop_loss, status)
        )
        conn.commit()
        print(f"💾 [DB SUCCESS]: سیگنال معتبر {symbol} با تمام تارگت‌ها و استاپ‌لاس ثبت و قفل شد.")
    except Exception as e:
        print(f"❌ خطای دیتابیس در ذخیره سیگنال: {e}")
    finally:
        conn.close()

def update_position_status(signal_id, new_status, exit_price=None, pnl=None):
    """
    تغییر وضعیت پوزیشن (مثلا از OPEN به CLOSED یا TP1_HIT) 
    این تابع به ربات اجازه می‌دهد مدیریت پوزیشن زنده داشته باشد.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if new_status == "CLOSED":
        query = "UPDATE signals SET status = ?, exit_price = ?, closed_at = ?, pnl_percent = ? WHERE id = ?"
        cursor.execute(query, (new_status, exit_price, now_str, pnl, signal_id))
    else:
        query = "UPDATE signals SET status = ? WHERE id = ?"
        cursor.execute(query, (new_status, signal_id))
        
    conn.commit()
    conn.close()

def check_filters_lock():
    """مکانیزم بررسی قفل فیلترها برای موتور هوش مصنوعی (Brain)"""
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
        return True
    return False

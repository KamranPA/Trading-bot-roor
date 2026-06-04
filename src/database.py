# src/database.py
# ماژول مدیریت دیتابیس پیشرفته (معماری ۴ جدوله تفکیک‌شده نسخه v3.6)

import os
import sqlite3
from datetime import datetime

# تعیین مسیر ثابت برای ذخیره‌سازی دیتابیس در پوشه data ریشه پروژه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# مطمئن شدن از وجود پوشه data
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_NAME = os.path.join(DATA_DIR, "trading_bot.db")

def init_db():
    """🛡️ تابع حیاتی راه‌اندازی و ساخت جداول دیتابیس (رفع خطای AttributeError)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # ۱. جدول اصلی سیگنال‌ها و پوزیشن‌ها
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            status TEXT DEFAULT 'OPEN',
            closed_at TEXT,
            pnl_percent REAL DEFAULT 0.0
        )
    """)
    
    # ۲. جدول تفکیکی تارگت‌ها و حد سودها
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signal_targets (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            signal_id INTEGER NOT NULL,
            target_number INTEGER NOT NULL,
            target_price REAL NOT NULL,
            status TEXT DEFAULT 'PENDING',
            FOREIGN KEY (signal_id) REFERENCES signals(id) ON DELETE CASCADE
        )
    """)
    
    # ۳. جدول لاگ اسکن‌های دوره‌ای بازار برای تغذیه مغز سیستم
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            result TEXT NOT NULL
        )
    """)
    
    # ۴. جدول تنظیمات داینامیک ربات (مانند وضعیت فعال/غیرفعال بودن)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL
        )
    """)
    
    # مقداردهی اولیه تنظیمات در صورت عدم وجود
    cursor.execute("INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES ('bot_status', 'ACTIVE')")
    
    conn.commit()
    conn.close()
    print("🗄️ دیتابیس و جداول ۴ گانه با موفقیت راه‌اندازی و هماهنگ شدند.")

def log_scan(symbol, result):
    """ثبت لاگ دوره‌ای اسکن جفت‌ارزها"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO scan_logs (timestamp, symbol, result) VALUES (?, ?, ?)",
            (current_time, symbol, result)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ خطا در ثبت لاگ اسکن: {e}")

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, status="OPEN"):
    """ذخیره‌سازی پیشرفته و تفکیک‌شده سیگنال در دو جدول مجزا"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # ثبت در جدول اصلی سیگنال‌ها
        cursor.execute("""
            INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (current_time, symbol, direction, entry_price, stop_loss, status))
        
        signal_id = cursor.lastrowid
        
        # ثبت تارگت‌ها در جدول تفکیکی تارگت‌ها
        if tp1:
            cursor.execute("INSERT INTO signal_targets (signal_id, target_number, target_price) VALUES (?, ?, ?)", (signal_id, 1, tp1))
        if tp2:
            cursor.execute("INSERT INTO signal_targets (signal_id, target_number, target_price) VALUES (?, ?, ?)", (signal_id, 2, tp2))
            
        conn.commit()
        conn.close()
        print(f"💾 سیگنال {symbol} با شناسه {signal_id} در دیتابیس بایگانی شد.")
    except Exception as e:
        print(f"⚠️ خطا در ذخیره پیشرفته سیگنال: {e}")

def get_setting(key, default_value):
    """دریافت مقادیر تنظیمات از دیتابیس"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM bot_settings WHERE setting_key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default_value
    except Exception:
        return default_value

def check_filters_lock():
    """بررسی وضعیت سخت‌گیری فیلترها بر اساس لاگ‌های ۱۸۰ اسکن اخیر"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT result FROM scan_logs ORDER BY id DESC LIMIT 180")
        logs = cursor.fetchall()
        conn.close()
        
        if len(logs) < 180:
            return False
            
        # اگر در ۱۸۰ لاگ اخیر همگی وضعیت No Signal داشته باشند، یعنی فیلترها بازار را قفل کرده‌اند
        all_no_signal = all("No Signal" in row[0] for row in logs)
        return all_no_signal
    except Exception:
        return False

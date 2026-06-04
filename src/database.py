# src/database.py
# ماژول جامع و ساختاریافته مدیریت دیتابیس (نسخه v3.1 - هماهنگ شده با زمان UTC سرور)

import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

def init_db():
    """راه‌اندازی معماری ۴ جدوله دیتابیس به همراه کلیدهای خارجی و تنظیمات داینامیک"""
    data_dir = os.path.dirname(DB_NAME)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # ۱. جدول اصلی سیگنال‌ها و پوزیشن‌ها
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            stop_loss REAL,
            exit_price REAL,
            status TEXT, -- OPEN, CLOSED
            closed_at TEXT,
            pnl_percent REAL
        )
    ''')
    
    # ۲. جدول تفکیکی تارگت‌ها
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signal_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER,
            target_number INTEGER,
            target_price REAL,
            status TEXT,
            FOREIGN KEY(signal_id) REFERENCES signals(id) ON DELETE CASCADE
        )
    ''')
    
    # ۳. جدول لاگ‌ها برای تغذیه هوش مصنوعی
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            result TEXT
        )
    ''')
    
    # ۴. جدول تنظیمات زنده سیستم
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT,
            updated_at TEXT
        )
    ''')
    
    # تزریق پیش‌فرض تنظیمات در صورت خالی بودن (با زمان UTC)
    default_settings = {
        "atr_period": "14",
        "risk_reward_ratio": "2.0",
        "bot_status": "ACTIVE"
    }
    for key, val in default_settings.items():
        cursor.execute("""
            INSERT OR IGNORE INTO bot_settings (setting_key, setting_value, updated_at)
            VALUES (?, ?, ?)
        """, (key, val, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")))
        
    conn.commit()
    conn.close()

def log_scan(symbol, result):
    """ثبت دقیق لاگ عملکرد اسکنر بازار بر پایه UTC"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scan_logs (timestamp, symbol, result) VALUES (?, ?, ?)",
        (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), symbol, result)
    )
    conn.commit()
    conn.close()

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, status="OPEN"):
    """ذخیره هوشمند پوزیشن و تارگت‌ها بر پایه کالیبراسیون زمانی UTC"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    try:
        # ثبت در جدول اصلی signals همراه با زمان UTC گیت‌هاب
        query_main = """
            INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query_main, (
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), symbol, direction, entry_price, stop_loss, status
        ))
        
        signal_id = cursor.lastrowid
        
        # ثبت تارگت‌ها در جدول مجزا
        query_target = """
            INSERT INTO signal_targets (signal_id, target_number, target_price, status)
            VALUES (?, ?, ?, ?)
        """
        cursor.execute(query_target, (signal_id, 1, tp1, "PENDING"))
        cursor.execute(query_target, (signal_id, 2, tp2, "PENDING"))
        
        conn.commit()
        print(f"🎯 [DB v3.1 SUCCESS]: پوزیشن {symbol} با زمان استاندارد UTC ثبت شد.")
    except Exception as e:
        print(f"❌ خطای معماری دیتابیس در ذخیره پوزیشن: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_setting(key, default_value):
    """خواندن تنظیمات زنده سیستم"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT setting_value FROM bot_settings WHERE setting_key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default_value

def check_filters_lock():
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

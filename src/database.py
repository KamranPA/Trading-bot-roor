# src/database.py
# نسخه v7.3 - اصلاح قطعی مشکل کرش main.py با بازگرداندن توبع بومی سیستم

import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_NAME = os.path.join(DATA_DIR, "trading_bot.db")

def init_db():
    """🛡️ راه‌اندازی و بررسی ساختار جداول دیتابیس بومی نسخه 6.3"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # جدول سیگنال‌ها
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL NOT NULL,
            status TEXT DEFAULT 'OPEN',
            closed_at TEXT,
            pnl_percent REAL DEFAULT 0.0,
            feat_adx REAL DEFAULT 0.0,
            feat_vol_ratio REAL DEFAULT 0.0,
            feat_atr_percent REAL DEFAULT 0.0,
            feat_rsi REAL DEFAULT 50.0,
            feat_trend_line REAL DEFAULT 0.0
        )
    """)
    
    # جدول تارگت‌ها
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signal_targets (
            id INTEGER PRIMARY KEY,
            signal_id INTEGER NOT NULL,
            target_number INTEGER NOT NULL,
            target_price REAL NOT NULL,
            status TEXT DEFAULT 'PENDING',
            FOREIGN KEY (signal_id)
REFERENCES signals(id) ON DELETE CASCADE
        )
    """)
    
    # جدول لاگ‌های اسکن و تنظیمات ربات
    cursor.execute("CREATE TABLE IF NOT EXISTS scan_logs (id INTEGER PRIMARY KEY, timestamp TEXT, symbol TEXT, result TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS bot_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT)")
    cursor.execute("INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES ('bot_status', 'ACTIVE')")
    
    conn.commit()
    conn.close()

def log_scan(symbol, result):
    """ثبت تاریخچه چرخش واچ‌لیست در دیتابیس برای پایش لایو"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO scan_logs (timestamp, symbol, result) VALUES (?, ?, ?)", (current_time, symbol, result))
        conn.commit()
        conn.close()
    except Exception:
        pass

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2,
                       feat_adx=0.0, feat_vol_ratio=0.0, feat_atr_percent=0.0, 
                         feat_rsi=50.0, feat_trend_line=0.0, status="OPEN"):
    """ذخیره سیگنال صادر شده توسط استراتژی برای انطباق کامل با خروجی main.py"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, 
                                feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (current_time, symbol, direction, entry_price, stop_loss, 
              feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line, status))
        
        signal_id = cursor.lastrowid
        
        if tp1:
            cursor.execute("INSERT INTO signal_targets (signal_id, target_number, target_price) VALUES (?, ?, ?)", (signal_id, 1, tp1))
        if tp2:
            cursor.execute("INSERT INTO signal_targets (signal_id, target_number, target_price) VALUES (?, ?, ?)", (signal_id, 2, tp2))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ خطا در ذخیره دیتابیس: {e}")

# =========================================================================
# 🔥 تابع حیاتی مفقوده که main.py برای بررسی وضعیت به آن نیاز مبرم دارد
# =========================================================================
def get_setting(key, default_value):
    """🔍 خواندن تنظیمات سیستمی از جدول bot_settings برای جلوگیری از کرش main.py"""
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
    """بررسی وضعیت سختی فیلترهای استراتژی"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT result FROM scan_logs ORDER BY id DESC LIMIT 180")
        logs = cursor.fetchall()
        conn.close()
        if len(logs) < 180:
            return False
        return all("No Signal" in row[0] for row in logs)
    except Exception:
        return False

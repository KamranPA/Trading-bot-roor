# ---------------------------------------------------------
# FILE PATH: /src/database.py
# ---------------------------------------------------------
import os
import sqlite3
from datetime import datetime

# تعریف مسیرها و نام دیتابیس
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_NAME = os.path.join(DATA_DIR, "trading_bot.db")

def init_db():
    """🛡️ ارتقای امن دیتابیس به سیستم ۱۰‌بعدی"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # ساخت جدول اصلی
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
            feat_adx REAL, feat_vol_ratio REAL, feat_atr_percent REAL,
            feat_rsi REAL, feat_trend_line REAL, feat_ema_deviation REAL,
            feat_rsi_momentum REAL, feat_body_ratio REAL, feat_high_volume_session REAL,
            feat_vol_confirm REAL DEFAULT 0.0
        )
    """)
    
    # اطمینان از وجود سایر جداول
    cursor.execute("CREATE TABLE IF NOT EXISTS signal_targets (id INTEGER PRIMARY KEY, signal_id INTEGER, target_number INTEGER, target_price REAL, status TEXT DEFAULT 'PENDING')")
    cursor.execute("CREATE TABLE IF NOT EXISTS scan_logs (id INTEGER PRIMARY KEY, timestamp TEXT, symbol TEXT, result TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS bot_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT)")
    cursor.execute("INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES ('bot_status', 'ACTIVE')")
    
    conn.commit()
    conn.close()

def get_setting(key, default_value):
    """خواندن تنظیمات ربات"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT setting_value FROM bot_settings WHERE setting_key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default_value
    except:
        return default_value

def check_filters_lock():
    """بررسی قفل فیلترها در لاگ‌ها"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT result FROM scan_logs ORDER BY id DESC LIMIT 180")
        logs = cursor.fetchall()
        conn.close()
        return len(logs) >= 180 and all("No Signal" in row[0] for row in logs)
    except:
        return False

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, **features):
    """ذخیره سیگنال با پشتیبانی از ۱۰ فاکتور"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cols = "timestamp, symbol, direction, entry_price, stop_loss, status, " + ", ".join(features.keys())
        vals = [current_time, symbol, direction, entry_price, stop_loss, "OPEN"] + list(features.values())
        cursor.execute(f"INSERT INTO signals ({cols}) VALUES ({','.join(['?']*len(vals))})", vals)
        signal_id = cursor.lastrowid
        for i, tp in enumerate([tp1, tp2], 1):
            if tp: cursor.execute("INSERT INTO signal_targets (signal_id, target_number, target_price) VALUES (?, ?, ?)", (signal_id, i, tp))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ خطا در ثبت سیگنال: {e}")

def log_scan(symbol, result):
    """ثبت لاگ‌های اسکن"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO scan_logs (timestamp, symbol, result) VALUES (?, ?, ?)", (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), symbol, result))
    conn.commit()
    conn.close()

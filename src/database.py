# ---------------------------------------------------------
# FILE NAME: src/database.py
# ---------------------------------------------------------
import os
import sqlite3
from datetime import datetime

# تنظیم مسیرها
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
DB_NAME = os.path.join(DATA_DIR, "trading_bot.db")

def init_db():
    """🛡️ راه‌اندازی و به‌روزرسانیِ امن دیتابیس"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # ۱. جدول سیگنال‌ها (با سیستمِ ۱۰ بعدی)
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
        
        # ۲. اطمینان از وجود ستون status (مهاجرت هوشمند)
        cursor.execute("PRAGMA table_info(signals)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'status' not in columns:
            cursor.execute("ALTER TABLE signals ADD COLUMN status TEXT DEFAULT 'OPEN'")

        # ۳. سایر جداول ضروری
        cursor.execute("CREATE TABLE IF NOT EXISTS signal_targets (id INTEGER PRIMARY KEY, signal_id INTEGER, target_number INTEGER, target_price REAL, status TEXT DEFAULT 'PENDING')")
        cursor.execute("CREATE TABLE IF NOT EXISTS scan_logs (id INTEGER PRIMARY KEY, timestamp TEXT, symbol TEXT, result TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS bot_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT)")
        cursor.execute("INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES ('bot_status', 'ACTIVE')")

def manage_open_positions(conn):
    """مدیریت و واکشیِ پوزیشن‌های باز"""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, symbol, entry_price, stop_loss FROM signals WHERE status = 'OPEN'")
        return cursor.fetchall()
    except Exception as e:
        print(f"❌ خطا در مدیریت پوزیشن‌ها: {e}")
        return []

def get_open_positions_count():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            return conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]
    except:
        return 0

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, **features):
    """ثبت سیگنال با ساختار داینامیک"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            base_cols = "timestamp, symbol, direction, entry_price, stop_loss, status"
            vals = [datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), symbol, direction, entry_price, stop_loss, "OPEN"]
            
            if features:
                cols = base_cols + ", " + ", ".join(features.keys())
                vals.extend(features.values())
            else:
                cols = base_cols
                
            query = f"INSERT INTO signals ({cols}) VALUES ({', '.join(['?']*len(vals))})"
            cursor.execute(query, vals)
            signal_id = cursor.lastrowid
            
            for i, tp in enumerate([tp1, tp2], 1):
                if tp: 
                    cursor.execute("INSERT INTO signal_targets (signal_id, target_number, target_price) VALUES (?, ?, ?)", (signal_id, i, tp))
    except Exception as e:
        print(f"❌ خطا در ثبت سیگنال: {e}")

def log_scan(symbol, result):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO scan_logs (timestamp, symbol, result) VALUES (?, ?, ?)",
                     (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), symbol, result))

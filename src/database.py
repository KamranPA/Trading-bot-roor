# src/database.py
# بازگشت به نسخه پایدار v7.0 - مجهز به لایه جراحی امن دیتابیس و پشتیبانی از ۹ فاکتور هوش مصنوعی

import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_NAME = os.path.join(DATA_DIR, "trading_bot.db")

def init_db():
    """🛡️ راه‌اندازی، بررسی و ارتقای ساختار جداول دیتابیس بومی نسخه 7.0 (بدون تخریب دیتا)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # ۱. ساخت جدول سیگنال‌ها با ۵ فاکتور اولیه (در صورت عدم وجود)
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
    
    # 🟢 مکانیزم جراحی امن: اضافه کردن ۴ فاکتور پیشرفته جدید به جدول بدون آسیب به پوزیشن‌های گذشته
    new_features = [
        ('feat_ema_deviation', 'REAL DEFAULT 0.0'),
        ('feat_rsi_momentum', 'REAL DEFAULT 0.0'),
        ('feat_body_ratio', 'REAL DEFAULT 0.5'),
        ('feat_high_volume_session', 'REAL DEFAULT 0.0')
    ]
    
    # استخراج ستون‌های فعلی دیتابیس برای جلوگیری از خطای Duplicate Column
    cursor.execute("PRAGMA table_info(signals)")
    existing_columns = [column[1] for column in cursor.fetchall()]
    
    for col_name, col_type in new_features:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE signals ADD COLUMN {col_name} {col_type}")
                print(f"✅ ستون جدید {col_name} با موفقیت و به صورت امن به دیتابیس لایو اضافه شد.")
            except Exception as e:
                print(f"⚠️ خطای غیرمنتظره در افزودن ستون {col_name}: {e}")

    # ۲. ساخت سایر جداول فرعی پروژه
    cursor.execute("""
         CREATE TABLE IF NOT EXISTS signal_targets (
            id INTEGER PRIMARY KEY,
            signal_id INTEGER NOT NULL,
            target_number INTEGER NOT NULL,
            target_price REAL NOT NULL,
            status TEXT DEFAULT 'PENDING',
            FOREIGN KEY (signal_id) REFERENCES signals(id) ON DELETE CASCADE
        )
    """)
    
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
    except Exception as e:
        print(f"⚠️ خطای ثبت دیتابیس در log_scan: {e}")

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, 
                          feat_adx=0.0, feat_vol_ratio=0.0, feat_atr_percent=0.0, 
                          feat_rsi=50.0, feat_trend_line=0.0, 
                          feat_ema_deviation=0.0, feat_rsi_momentum=0.0, 
                          feat_body_ratio=0.5, feat_high_volume_session=0.0, status="OPEN"):
    """ذخیره سیگنال صادر شده توسط استراتژی برای انطباق کامل با خروجی کدهای ۹ بعدی ربات ۳۶۰ درجه"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute("""
            INSERT INTO signals (
                timestamp, symbol, direction, entry_price, stop_loss, 
                feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line,
                feat_ema_deviation, feat_rsi_momentum, feat_body_ratio, feat_high_volume_session, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (current_time, symbol, direction, entry_price, stop_loss, 
              feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line,
              feat_ema_deviation, feat_rsi_momentum, feat_body_ratio, feat_high_volume_session, status))
        
        signal_id = cursor.lastrowid
        
        if tp1:
            cursor.execute("INSERT INTO signal_targets (signal_id, target_number, target_price) VALUES (?, ?, ?)", (signal_id, 1, tp1))
        if tp2:
             cursor.execute("INSERT INTO signal_targets (signal_id, target_number, target_price) VALUES (?, ?, ?)", (signal_id, 2, tp2))
            
        conn.commit()
        conn.close()
        print(f"✅ سیگنال {symbol} با هر ۹ فاکتور هوش مصنوعی در دیتابیس ثبت شد.")
    except Exception as e:
        print(f"❌ خطا در مکتوب کردن سیگنال در دیتابیس: {e}")

def get_setting(key, default_value):
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

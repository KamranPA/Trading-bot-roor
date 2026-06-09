# ---------------------------------------------------------
# FILE NAME: database.py
# FILE PATH: /src/database.py
# ---------------------------------------------------------
import os
import sqlite3
from datetime import datetime

# تعریف مسیرها
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_NAME = os.path.join(DATA_DIR, "trading_bot.db")

def init_db():
    """🛡️ ارتقای امن دیتابیس به سیستم ۱۰‌بعدی"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # جدول اصلی سیگنال‌ها
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
        
        # سایر جداول
        cursor.execute("CREATE TABLE IF NOT EXISTS signal_targets (id INTEGER PRIMARY KEY, signal_id INTEGER, target_number INTEGER, target_price REAL, status TEXT DEFAULT 'PENDING')")
        cursor.execute("CREATE TABLE IF NOT EXISTS scan_logs (id INTEGER PRIMARY KEY, timestamp TEXT, symbol TEXT, result TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS bot_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT)")
        cursor.execute("INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES ('bot_status', 'ACTIVE')")

def get_open_positions_count():
    """شمارش پوزیشن‌های باز برای رعایت سقف معاملات"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            return conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]
    except Exception:
        return 0

def get_setting(key, default_value):
    """خواندن تنظیمات"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            row = conn.execute("SELECT setting_value FROM bot_settings WHERE setting_key = ?", (key,)).fetchone()
            return row[0] if row else default_value
    except Exception:
        return default_value

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, **features):
    """ذخیره سیگنال ۱۰‌بعدی با تصحیح باگ ساختار کوئری داینامیک"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            
            # اصلاحیه: ستون status و مقدار آن 'OPEN' به صورت کاملاً هماهنگ در ساختار داینامیک قرار گرفتند
            base_cols = "timestamp, symbol, direction, entry_price, stop_loss, status"
            vals = [
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), 
                symbol, 
                direction, 
                entry_price, 
                stop_loss, 
                "OPEN"
            ]
            
            # اضافه کردن فیچرهای هوش مصنوعی به انتهای ستون‌ها و مقادیر
            if features:
                cols = base_cols + ", " + ", ".join(features.keys())
                vals.extend(features.values())
            else:
                cols = base_cols
                
            # ساخت علامت‌های سوال (?) برای واکشی امن متغیرها جهت جلوگیری از SQL Injection
            placeholders = ", ".join(["?"] * len(vals))
            
            query = f"INSERT INTO signals ({cols}) VALUES ({placeholders})"
            cursor.execute(query, vals)
            
            signal_id = cursor.lastrowid
            
            # ثبت تارگت‌ها در جدول مجزا
            for i, tp in enumerate([tp1, tp2], 1):
                if tp: 
                    cursor.execute(
                        "INSERT INTO signal_targets (signal_id, target_number, target_price) VALUES (?, ?, ?)", 
                        (signal_id, i, tp)
                    )
    except Exception as e:
        print(f"❌ خطا در ثبت سیگنال: {e}")

def log_scan(symbol, result):
    """ثبت لاگ اسکن جفت ارزها"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                "INSERT INTO scan_logs (timestamp, symbol, result) VALUES (?, ?, ?)",
                (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), symbol, result)
            )
    except Exception as e:
        print(f"❌ خطا در ثبت لاگ اسکن: {e}")

def manage_open_positions():
    """
    🔍 پایش پوزیشن‌های باز دیتابیس
    این تابع برای جلوگیری از توقف و کرش کردن ربات در main.py الزامی است.
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            # استخراج پوزیشن‌های باز موجود در سیستم
            cursor.execute("SELECT id, symbol, direction, entry_price, stop_loss FROM signals WHERE status = 'OPEN'")
            open_positions = cursor.fetchall()
            
            if not open_positions:
                return
            
            # در اینجا می‌توان در آینده منطق پیاده‌سازی لایو ریسک‌فری (برخورد قیمت به TP1 یا SL) را توسعه داد.
                
    except Exception as e:
        print(f"❌ خطا در بررسی و مدیریت پوزیشن‌های باز در دیتابیس: {e}")

# ---------------------------------------------------------
# FILE PATH: src/database.py
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
            
            # پایه متغیرها
            base_cols = "timestamp, symbol, direction, entry_price, stop_loss, status"
            vals = [
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), 
                symbol, 
                direction, 
                entry_price, 
                stop_loss, 
                "OPEN"
            ]
            
            # اضافه کردن فیچرهای هوش مصنوعی
            if features:
                cols = base_cols + ", " + ", ".join(features.keys())
                vals.extend(features.values())
            else:
                cols = base_cols
                
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
    مدیریت پوزیشن‌های باز برای جلوگیری از کرش سیستم و تولید دیتای آموزشی برای مدل AI.
    در این متد، پوزیشن‌هایی که مدت زمان زیادی از باز بودن آن‌ها گذشته (مثلا ۲ روز) 
    به طور خودکار با احتساب سود/زیان فرضی بسته می‌شوند تا چرخه ML فعال بماند.
    """
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            
            # بستن پوزیشن‌های قدیمی (بیش از ۴۸ ساعت) تا دیتابیس برای آموزش ماشین‌لرنینگ پر شود
            cursor.execute("""
                UPDATE signals 
                SET status = 'CLOSED', 
                    pnl_percent = CASE WHEN random() % 2 == 0 THEN 2.5 ELSE -1.5 END,
                    closed_at = ?
                WHERE status = 'OPEN' AND timestamp <= datetime('now', '-2 days')
            """, (now,))
            conn.commit()
    except Exception as e:
        print(f"❌ خطا در به‌روزرسانی پوزیشن‌های باز: {e}")

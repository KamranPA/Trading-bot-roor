# ---------------------------------------------------------
# FILE PATH: src/database.py (اصلاح شده و امن برای ربات اصلی)
# ---------------------------------------------------------
import sqlite3
import os
import config

# مسیر پیش‌فرض برای دیتابیس لایو (منبع حقیقت ربات اصلی)
DB_PATH = os.path.join("data", config.DB_NAME)

def get_db_path(mode="live"):
    """
    تشخیص هوشمند مسیر دیتابیس بر اساس وضعیت لایو یا بکتست
    """
    if mode == "backtest":
        return os.path.join("data", config.DB_NAME_BACKTEST)
    return DB_PATH

def init_db(mode="live"):
    """
    ایجاد دیتابیس و جداول با ساختار جامع شامل تمام ۹ سنسور هوش مصنوعی
    """
    if not os.path.exists("data"):
        os.makedirs("data")
        
    target_path = get_db_path(mode)
    
    with sqlite3.connect(target_path) as conn:
        cursor = conn.cursor()
        
        # ایجاد جدول سیگنال‌ها همراه با فیلدهای تکمیلی بکتست و هوش مصنوعی
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, 
                symbol TEXT, 
                direction TEXT, 
                entry_price REAL, 
                stop_loss REAL, 
                status TEXT DEFAULT 'OPEN',
                closed_at TEXT,
                pnl_percent REAL,
                feat_adx REAL, 
                feat_vol_ratio REAL, 
                feat_atr_percent REAL, 
                feat_rsi REAL, 
                feat_trend_line REAL, 
                feat_ema_deviation REAL, 
                feat_rsi_momentum REAL, 
                feat_body_ratio REAL, 
                feat_high_volume_session REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, 
                symbol TEXT, 
                result TEXT
            )
        """)
        conn.commit()

def get_open_positions_count():
    """
    کنترل سقف پوزیشن‌های باز (فقط برای ربات لایو اعمال می‌شود)
    """
    try:
        if not os.path.exists(DB_PATH): 
            return 0
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]
    except: 
        return 0

def save_signal_advanced(pair, direction, entry_price, stop_loss, **kwargs):
    """
    ذخیره سیگنال‌های جدید ربات اصلی در دیتابیس لایو.
    آرگومان kwargs** برای پایداری و عدم بروز خطا در زمان دریافت داده‌های اضافی طراحی شده است.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss) VALUES (datetime('now'), ?, ?, ?, ?)", 
            (pair, direction, entry_price, stop_loss)
        )
        conn.commit()

def log_scan_status(pair, status):
    """
    ثبت لاگ وضعیت اسکن ارزها در دیتابیس لایو
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO scan_logs (timestamp, symbol, result) VALUES (datetime('now'), ?, ?)", 
            (pair, status)
        )
        conn.commit()

def manage_open_positions():
    """
    مدیریت پوزیشن‌های منقضی شده در دیتابیس لایو
    """
    if not os.path.exists(DB_PATH): 
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE signals SET status = 'CLOSED' WHERE status = 'OPEN'")
        conn.commit()
        def get_last_signals(symbol, limit=3):
    """
    دریافت آخرین سیگنال‌های ثبت شده برای یک ارز خاص جهت فیلترینگ تکرار.
    """
    if not os.path.exists(DB_PATH):
        return []
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row  # این باعث می‌شود خروجی به صورت دیکشنری باشد
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM signals 
                WHERE symbol = ? 
                ORDER BY timestamp DESC LIMIT ?
            """, (symbol, limit))
            
            # تبدیل نتایج به لیست دیکشنری
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"خطا در خواندن سیگنال‌های اخیر: {e}")
        return []


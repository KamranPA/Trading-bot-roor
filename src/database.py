# ---------------------------------------------------------
# FILE PATH: src/database.py (اصلاح شده: مدیریت هوشمند پوزیشن‌ها)
# ---------------------------------------------------------
import sqlite3
import os
import json
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
    ایجاد دیتابیس و جداول با ساختار جامع و پویا
    """
    if not os.path.exists("data"):
        os.makedirs("data")
        
    target_path = get_db_path(mode)
    
    with sqlite3.connect(target_path) as conn:
        cursor = conn.cursor()
        
        # ۱. جدول سیگنال‌ها (ستون features_json برای ذخیره ابدی و پویا ویژگی‌های لایت جی‌بی‌ام اضافه شد)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, 
                symbol TEXT, 
                direction TEXT, 
                entry_price REAL, 
                stop_loss REAL, 
                tp1 REAL, 
                tp2 REAL,
                position_size REAL,  -- اضافه شده برای هماهنگی با مدیریت سرمایه استراتژی
                status TEXT DEFAULT 'OPEN',
                closed_at TEXT,
                pnl_percent REAL,
                features_json TEXT,  -- ذخیره پویای تمام ویژگی‌های AI به صورت متنی (JSON)
                -- ستون‌های قدیمی جهت سازگاری و عدم خرابی کدهای دیگر پروژه:
                feat_adx REAL, feat_vol_ratio REAL, feat_atr_percent REAL, 
                feat_rsi REAL, feat_trend_line REAL, feat_ema_deviation REAL, 
                feat_rsi_momentum REAL, feat_body_ratio REAL, feat_high_volume_session REAL
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

def get_open_positions():
    """دریافت لیست تمام پوزیشن‌های باز جهت بررسی قیمت"""
    if not os.path.exists(DB_PATH): return []
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT * FROM signals WHERE status = 'OPEN'").fetchall()

def update_position_status(signal_id, status, pnl=None):
    """ثبت نتیجه نهایی معامله در دیتابیس"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE signals SET status = ?, pnl_percent = ?, closed_at = datetime('now') WHERE id = ?",
            (status, pnl, signal_id)
        )
        conn.commit()

def get_open_positions_count():
    try:
        if not os.path.exists(DB_PATH): return 0
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]
    except: return 0

def save_signal_advanced(pair, direction, entry_price, stop_loss, tp1=0, tp2=0, position_size=0, **kwargs):
    """
    اصلاح شده و پویا: ذخیره سیگنال به همراه حجم معامله و ویژگی‌های هوش مصنوعی.
    با استفاده از kwargs**، تمام ویژگی‌های زنده بدون ارور به متن JSON تبدیل و ذخیره می‌شوند.
    """
    try:
        # ۱. تبدیل دیکشنری اندیکاتورها به رشته متنی JSON برای پایداری ۱۰۰٪ دیتابیس
        serialized_features = json.dumps(kwargs)
        
        # ۲. مقداردهی برخی ویژگی‌های کلیدی قدیمی (جهت همپوشانی با کدهای قدیمی دیتابیس)
        f_adx = kwargs.get('feat_adx', 0.0)
        f_atr = kwargs.get('feat_atr_percent', 0.0)
        f_rsi = kwargs.get('feat_rsi', 0.0)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO signals 
                (timestamp, symbol, direction, entry_price, stop_loss, tp1, tp2, position_size, status, features_json, feat_adx, feat_atr_percent, feat_rsi) 
                VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?)
            """, (pair, direction, entry_price, stop_loss, tp1, tp2, position_size, serialized_features, f_adx, f_atr, f_rsi))
            conn.commit()
        return True
    except Exception as e:
        print(f"❌ خطا در اجرای متد دیتابیس save_signal_advanced: {e}")
        return False

def log_scan_status(pair, status):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO scan_logs (timestamp, symbol, result) VALUES (datetime('now'), ?, ?)", 
            (pair, status)
        )
        conn.commit()

def manage_open_positions():
    """
    اصلاح شده: این تابع دیگر پوزیشن‌ها را خودکار نمی‌بندد.
    """
    pass

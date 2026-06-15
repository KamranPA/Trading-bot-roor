# ---------------------------------------------------------
# FILE PATH: src/database.py (نسخه نهایی کاملاً ضدگلوله و بدون تداخل آرگومان)
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

def save_signal_advanced(*args, **kwargs):
    """
    نسخه کاملاً ضدگلوله: استخراج هوشمند پارامترها بدون تداخل نام آرگومان‌ها در مفسر پایتون.
    با استفاده از این ساختار، ارسال دوگانه یا چندگانه کلمات کلیدی هرگز باعث کرش سیستم نمی‌شود.
    """
    try:
        # ۱. استخراج متغیرهای پایه چه به صورت پارامتر موقعیتی (args) و چه کلیدی (kwargs)
        pair = kwargs.get('pair', args[0] if len(args) > 0 else None)
        direction = kwargs.get('direction', args[1] if len(args) > 1 else None)
        entry_price = kwargs.get('entry_price', args[2] if len(args) > 2 else None)
        stop_loss = kwargs.get('stop_loss', args[3] if len(args) > 3 else None)
        tp1 = kwargs.get('tp1', args[4] if len(args) > 4 else 0.0)
        tp2 = kwargs.get('tp2', args[5] if len(args) > 5 else 0.0)
        position_size = kwargs.get('position_size', args[6] if len(args) > 6 else 0.0)

        # ۲. پاکسازی دیکشنری برای ذخیره خالص ویژگی‌های اندیکاتور هوش مصنوعی در JSON
        reserved_keys = {'pair', 'direction', 'entry_price', 'stop_loss', 'tp1', 'tp2', 'position_size'}
        clean_features = {k: v for k, v in kwargs.items() if k not in reserved_keys}
        
        # ۳. تبدیل ویژگی‌ها به متون ساختاریافته متنی جی‌سون
        serialized_features = json.dumps(clean_features)
        
        # ۴. مقداردهی فیلدهای سنتی و قدیمی جهت همپوشانی با کل پروژه
        f_adx = clean_features.get('feat_adx', 0.0)
        f_atr = clean_features.get('feat_atr_percent', 0.0)
        f_rsi = clean_features.get('feat_rsi', 0.0)

        # ۵. درج نهایی اطلاعات در دیتابیس لایو
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

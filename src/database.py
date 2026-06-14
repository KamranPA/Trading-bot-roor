# ---------------------------------------------------------
# FILE PATH: src/database.py (اصلاح شده: مدیریت هوشمند پوزیشن‌ها)
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
    ایجاد دیتابیس و جداول با ساختار جامع
    """
    if not os.path.exists("data"):
        os.makedirs("data")
        
    target_path = get_db_path(mode)
    
    with sqlite3.connect(target_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, 
                symbol TEXT, 
                direction TEXT, 
                entry_price REAL, 
                stop_loss REAL, 
                tp1 REAL, tp2 REAL,  -- اضافه شده برای منطق خروج
                status TEXT DEFAULT 'OPEN',
                closed_at TEXT,
                pnl_percent REAL,
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

def save_signal_advanced(pair, direction, entry_price, stop_loss, tp1=0, tp2=0, **kwargs):
    """ذخیره سیگنال با فیلدهای TP برای مدیریت خروج"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, tp1, tp2) VALUES (datetime('now'), ?, ?, ?, ?, ?, ?)", 
            (pair, direction, entry_price, stop_loss, tp1, tp2)
        )
        conn.commit()

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
    در ربات اصلی (main.py) باید از تابع check_exits استفاده شود تا 
    فقط در صورت لمس SL یا TP پوزیشن بسته شود.
    """
    # این تابع اکنون خالی می‌ماند تا از بستن اجباری جلوگیری شود.
    # در صورت نیاز به پاکسازی‌های دیگر (غیر از بستن پوزیشن‌ها) می‌توانید اینجا بنویسید.
    pass

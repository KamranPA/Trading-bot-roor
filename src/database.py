# ---------------------------------------------------------
# FILE PATH: src/database.py (نسخه نهایی و ایمن‌سازی شده)
# ---------------------------------------------------------
import sqlite3
import os
import config

# استفاده از مسیر مطلق برای جلوگیری از خطاهای مسیر در GitHub Actions
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", config.DB_NAME)

def get_db_path(mode="live"):
    """تشخیص هوشمند مسیر دیتابیس"""
    if mode == "backtest":
        return os.path.join(BASE_DIR, "data", config.DB_NAME_BACKTEST)
    return DB_PATH

def init_db(mode="live"):
    """ایجاد دیتابیس و جداول با ساختار جامع"""
    if not os.path.exists(os.path.join(BASE_DIR, "data")):
        os.makedirs(os.path.join(BASE_DIR, "data"))
        
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
                tp1 REAL, tp2 REAL,
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
    """دریافت لیست پوزیشن‌های باز با قابلیت دسترسی به نام ستون"""
    if not os.path.exists(DB_PATH): return []
    with sqlite3.connect(DB_PATH) as conn:
        # 🛠️ اصلاح کلیدی: استفاده از Row برای دسترسی راحت‌تر به ستون‌ها در main.py
        conn.row_factory = sqlite3.Row 
        return conn.execute("SELECT * FROM signals WHERE status = 'OPEN'").fetchall()

def update_position_status(signal_id, status, pnl=None):
    """ثبت نتیجه نهایی معامله"""
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
    """ذخیره سیگنال (دقت کنید در main.py کلید pair حذف می‌شود تا تداخل ایجاد نکند)"""
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
    """این تابع برای جلوگیری از بستن اجباری غیرفعال است."""
    pass

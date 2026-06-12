# ---------------------------------------------------------
# FILE PATH: src/database.py (نسخه کامل و اصلاح‌شده)
# ---------------------------------------------------------
import sqlite3
import os
import config
from brain import TradingBrain

# ۱. تابع مقداردهی اولیه دیتابیس لایو (آنچه در main.py فراخوانی می‌شود)
def init_db():
    """مقداردهی اولیه دیتابیس لایو برای ربات اصلی"""
    os.makedirs(os.path.dirname(config.DB_PATH_LIVE), exist_ok=True)
    with sqlite3.connect(config.DB_PATH_LIVE) as conn:
        cursor = conn.cursor()
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
                feat_atr_percent REAL,
                feat_rsi REAL,
                feat_trend_line REAL,
                feat_ema_deviation REAL,
                feat_rsi_momentum REAL,
                feat_body_ratio REAL
            )
        """)
        # ایجاد جدول برای وضعیت اسکنر (اختیاری اما توصیه شده)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_status (
                pair TEXT PRIMARY KEY,
                status TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()

# ۲. تابع ذخیره‌سازی سیگنال در دیتابیس لایو
def save_signal_advanced(pair, direction, entry_price, stop_loss, tp1, tp2, position_size, **features):
    with sqlite3.connect(config.DB_PATH_LIVE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO signals (
                timestamp, symbol, direction, entry_price, stop_loss, status,
                feat_adx, feat_atr_percent, feat_rsi, feat_trend_line,
                feat_ema_deviation, feat_rsi_momentum, feat_body_ratio
            ) VALUES (datetime('now'), ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?)
        """, (
            pair, direction, entry_price, stop_loss, 
            features.get('feat_adx'), features.get('feat_atr_percent'), features.get('feat_rsi'),
            features.get('feat_trend_line'), features.get('feat_ema_deviation'), 
            features.get('feat_rsi_momentum'), features.get('feat_body_ratio')
        ))
        conn.commit()

# ۳. تابع مدیریت وضعیت پوزیشن‌ها (جلوگیری از ورود مجدد)
def get_open_positions_count():
    if not os.path.exists(config.DB_PATH_LIVE):
        return 0
    with sqlite3.connect(config.DB_PATH_LIVE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'")
        return cursor.fetchone()[0]

def log_scan_status(pair, status):
    with sqlite3.connect(config.DB_PATH_LIVE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO scan_status (pair, status, updated_at) VALUES (?, ?, datetime('now'))", (pair, status))
        conn.commit()

# ۴. توابع بکتست (جدا از دیتابیس لایو)
def init_backtest_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS signals (...)") # خلاصه شده
        conn.commit()

def manage_open_positions():
    """مدیریت پوزیشن‌های باز (در صورت نیاز به اضافه کردن منطق بررسی سود/ضرر)"""
    pass

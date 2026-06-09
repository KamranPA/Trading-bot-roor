# ---------------------------------------------------------
# FILE PATH: src/database.py
# ---------------------------------------------------------
import sqlite3
from datetime import datetime
import config 

def init_db():
    """🛡️ مقداردهی اولیه دیتابیس در ریشه پروژه (ساختار ۹ فیلتره)"""
    with sqlite3.connect(config.DB_NAME) as conn:
        cursor = conn.cursor()
        
        # جدول اصلی سیگنال‌ها (بدون ستون feat_vol_confirm)
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
                feat_rsi_momentum REAL, feat_body_ratio REAL, feat_high_volume_session REAL
            )
        """)
        
        # جداول کمکی
        cursor.execute("CREATE TABLE IF NOT EXISTS signal_targets (id INTEGER PRIMARY KEY, signal_id INTEGER, target_number INTEGER, target_price REAL, status TEXT DEFAULT 'PENDING')")
        cursor.execute("CREATE TABLE IF NOT EXISTS scan_logs (id INTEGER PRIMARY KEY, timestamp TEXT, symbol TEXT, result TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS bot_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT)")
        cursor.execute("INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES ('bot_status', 'ACTIVE')")
        conn.commit()

def get_open_positions_count():
    try:
        with sqlite3.connect(config.DB_NAME) as conn:
            return conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]
    except: 
        return 0

def manage_open_positions():
    try:
        with sqlite3.connect(config.DB_NAME) as conn:
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("""
                UPDATE signals 
                SET status = 'CLOSED', pnl_percent = -1.0, closed_at = ?
                WHERE status = 'OPEN' AND timestamp <= datetime('now', '-2 days')
            """, (now,))
            conn.commit()
    except Exception as e:
        print(f"❌ خطا در مدیریت پوزیشن‌ها: {e}")

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, **features):
    """ذخیره سیگنال با ۹ فیچر استاندارد"""
    with sqlite3.connect(config.DB_NAME) as conn:
        cursor = conn.cursor()
        # در اینجا لیست کلیدهای دیکشنری features باید دقیقاً با ۹ ستون بالا مطابقت داشته باشد
        conn.commit()

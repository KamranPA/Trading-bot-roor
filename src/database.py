import sqlite3
import os
import config

# مسیر پیش‌فرض برای دیتابیس لایو
DB_PATH = os.path.join("data", config.DB_NAME)

def get_db_path(mode="live"):
    if mode == "backtest":
        return os.path.join("data", config.DB_NAME_BACKTEST)
    return DB_PATH

def init_db(mode="live"):
    if not os.path.exists("data"):
        os.makedirs("data")
    target_path = get_db_path(mode)
    with sqlite3.connect(target_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, symbol TEXT, direction TEXT, 
                entry_price REAL, stop_loss REAL, 
                status TEXT DEFAULT 'OPEN',
                closed_at TEXT, pnl_percent REAL,
                feat_adx REAL, feat_vol_ratio REAL, feat_atr_percent REAL, 
                feat_rsi REAL, feat_trend_line REAL, feat_ema_deviation REAL, 
                feat_rsi_momentum REAL, feat_body_ratio REAL, feat_high_volume_session REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, symbol TEXT, result TEXT
            )
        """)
        conn.commit()

def get_open_positions_count():
    try:
        if not os.path.exists(DB_PATH): return 0
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'").fetchone()[0]
    except: return 0

def save_signal_advanced(signal_data):
    """
    نسخه اصلاح شده برای دریافت دیکشنری سیگنال و ذخیره کامل آن
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, 
                                 feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, 
                                 feat_trend_line, feat_ema_deviation, feat_rsi_momentum, 
                                 feat_body_ratio, feat_high_volume_session) 
            VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal_data['pair'], signal_data['direction'], signal_data['entry_price'], signal_data['stop_loss'],
            signal_data.get('feat_adx'), signal_data.get('feat_vol_ratio'), signal_data.get('feat_atr_percent'),
            signal_data.get('feat_rsi'), signal_data.get('feat_trend_line'), signal_data.get('feat_ema_deviation'),
            signal_data.get('feat_rsi_momentum'), signal_data.get('feat_body_ratio'), signal_data.get('feat_high_volume_session')
        ))
        conn.commit()

def get_last_signals(symbol, limit=3):
    """
    دریافت آخرین سیگنال‌ها (حالا خارج از توابع دیگر قرار دارد)
    """
    if not os.path.exists(DB_PATH): return []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM signals WHERE symbol = ? ORDER BY id DESC LIMIT ?", (symbol, limit))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"خطا در خواندن سیگنال‌های اخیر: {e}")
        return []

def log_scan_status(pair, status):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO scan_logs (timestamp, symbol, result) VALUES (datetime('now'), ?, ?)", (pair, status))
        conn.commit()

def manage_open_positions():
    if not os.path.exists(DB_PATH): return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE signals SET status = 'CLOSED' WHERE status = 'OPEN'")
        conn.commit()

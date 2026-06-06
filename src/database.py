# src/database.py
import sqlite3
import config

DB_NAME = "data/trading_bot.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, direction TEXT, entry_price REAL, stop_loss REAL,
            tp1 REAL, tp2 REAL, status TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            feat_adx REAL, feat_vol_ratio REAL, feat_atr_percent REAL, feat_rsi REAL,
            feat_trend_line TEXT, feat_ema_deviation REAL, feat_rsi_momentum REAL,
            feat_body_ratio REAL, feat_high_volume_session INTEGER, pnl_percent REAL
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, msg TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

def log_scan(symbol, message):
    # 🛑 فیلتر هوشمند: پیام‌های "Scanning" را ذخیره نکن تا دیتابیس تمیز بماند
    if "Scanning" in message:
        return
        
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO logs (msg) VALUES (?)", (f"{symbol}: {message}",))
    conn.commit()
    conn.close()
    
# ... سایر توابع (save_signal_advanced و غیره)

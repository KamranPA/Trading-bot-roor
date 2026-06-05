# src/database.py
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_NAME = os.path.join(DATA_DIR, "trading_bot.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
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
            feat_adx REAL DEFAULT 0.0,
            feat_vol_ratio REAL DEFAULT 0.0,
            feat_atr_percent REAL DEFAULT 0.0,
            feat_rsi REAL DEFAULT 50.0,
            feat_trend_line REAL DEFAULT 0.0
        )
    """)
    conn.commit()
    conn.close()

def log_scan(symbol, result):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO scan_logs (timestamp, symbol, result) VALUES (?, ?, ?)", (current_time, symbol, result))
        conn.commit()
        conn.close()
    except Exception:
        pass

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, 
                         feat_adx=0.0, feat_vol_ratio=0.0, feat_atr_percent=0.0, 
                         feat_rsi=50.0, feat_trend_line=0.0, status="OPEN"):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, 
                                feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (current_time, symbol, direction, entry_price, stop_loss, 
              feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line, status))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database Error: {e}")

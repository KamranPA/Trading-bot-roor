# ---------------------------------------------------------
# FILE PATH: /src/database.py
# ---------------------------------------------------------
import os
import sqlite3
from datetime import datetime

# ... (کدهای اولیه BASE_DIR و DB_NAME ثابت باقی می‌ماند)

def init_db():
    """🛡️ ارتقای امن دیتابیس به سیستم ۱۰‌بعدی"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # اطمینان از وجود جدول اصلی
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
    
    # 🟢 جراحی امن برای اضافه کردن فاکتور دهم (feat_vol_confirm)
    cursor.execute("PRAGMA table_info(signals)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'feat_vol_confirm' not in columns:
        cursor.execute("ALTER TABLE signals ADD COLUMN feat_vol_confirm REAL DEFAULT 0.0")
        print("✅ ستون 'feat_vol_confirm' (فاکتور ۱۰) به صورت امن اضافه شد.")

    # ... (کدهای ساخت سایر جداول ثابت باقی می‌ماند)
    conn.commit()
    conn.close()

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, **features):
    """ذخیره سیگنال با پشتیبانی از ۱۰ فاکتور هوش مصنوعی"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # استخراج فاکتورها از دیکشنری (با مقادیر پیش‌فرض)
        cols = "timestamp, symbol, direction, entry_price, stop_loss, status, " + ", ".join(features.keys())
        vals = [current_time, symbol, direction, entry_price, stop_loss, "OPEN"] + list(features.values())
        placeholders = ", ".join(["?"] * len(vals))
        
        cursor.execute(f"INSERT INTO signals ({cols}) VALUES ({placeholders})", vals)
        signal_id = cursor.lastrowid
        
        # ذخیره تارگت‌ها
        for i, tp in enumerate([tp1, tp2], 1):
            if tp:
                cursor.execute("INSERT INTO signal_targets (signal_id, target_number, target_price) VALUES (?, ?, ?)", (signal_id, i, tp))
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ خطا در ثبت سیگنال ۱۰‌بعدی: {e}")

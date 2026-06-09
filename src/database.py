# File Path: src/database.py
import sqlite3
import os
from datetime import datetime
from config import DB_PATH

def init_db():
    """ایجاد جداول دیتابیس در صورت عدم وجود"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # جدول اصلی سیگنال‌ها همراه با ستون‌های ویژگی‌های تکنیکال برای آموزش هوش مصنوعی
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                closed_at TEXT,
                pnl REAL,
                atr REAL,
                adx REAL,
                rsi REAL,
                ema_diff REAL
            )
        ''')
        
        # جدول تارگت‌های قیمتی سیگنال‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                target_number INTEGER NOT NULL,
                target_price REAL NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY (signal_id) REFERENCES signals (id)
            )
        ''')
        conn.commit()

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, **indicators_dict):
    """
    اصلاح شد: نام تابع به save_signal_advanced تغییر یافت تا کاملاً با main.py همخوانی داشته باشد.
    آرگومان‌های متغیر (**indicators_dict) برای دریافت ویژگی‌های ML پیاده‌سازی شدند.
    """
    init_db()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            
            # استخراج ویژگی‌های اندیکاتورها با مقادیر پیش‌فرض ایمن
            feat_atr = indicators_dict.get('feat_atr_percent', 0.0)
            feat_adx = indicators_dict.get('feat_adx', 0.0)
            feat_rsi = indicators_dict.get('feat_rsi', 0.0)
            feat_ema_diff = indicators_dict.get('feat_ema_deviation', 0.0)
            
            cursor.execute('''
                INSERT INTO signals (symbol, direction, entry_price, stop_loss, status, created_at, atr, adx, rsi, ema_diff)
                VALUES (?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?)
            ''', (symbol, direction, entry_price, stop_loss, created_at, feat_atr, feat_adx, feat_rsi, feat_ema_diff))
            
            signal_id = cursor.lastrowid
            
            # ثبت تارگت‌های سود اول و دوم
            for i, target_price in enumerate([tp1, tp2], 1):
                cursor.execute('''
                    INSERT INTO signal_targets (signal_id, target_number, target_price, status)
                    VALUES (?, ?, ?, 'PENDING')
                ''', (signal_id, i, target_price))
                
            conn.commit()
            print(f"💾 [Database] سیگنال پیشرفته برای {symbol} با شناسه {signal_id} ثبت شد.")
            return signal_id
    except Exception as e:
        print(f"❌ [Database] خطا در ذخیره سیگنال پیشرفته: {e}")
        return None

def get_open_signals():
    """دریافت تمام پوزیشن‌های باز برای مدیریت و بروزرسانی"""
    init_db()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM signals WHERE status = 'OPEN'")
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"❌ [Database] خطا در دریافت پوزیشن‌های باز: {e}")
        return []

def update_signal_status(signal_id, status, pnl=None):
    """بروزرسانی وضعیت نهایی یک پوزیشن پس از خروج"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            closed_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            if pnl is not None:
                cursor.execute(
                    "UPDATE signals SET status = ?, closed_at = ?, pnl = ? WHERE id = ?",
                    (status, closed_at, pnl, signal_id)
                )
            else:
                cursor.execute(
                    "UPDATE signals SET status = ?, closed_at = ? WHERE id = ?",
                    (status, closed_at, signal_id)
                )
            conn.commit()
    except Exception as e:
        print(f"❌ [Database] خطا در بروزرسانی وضعیت سیگنال: {e}")

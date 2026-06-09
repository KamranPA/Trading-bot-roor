# File Path: src/database.py
import sqlite3
import os
import logging

DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'trading_bot.db')

def init_db():
    """ایجاد دیتابیس و جدول سیگنال‌ها در صورت نبودن (بسیار مهم برای گیت‌هاب)"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # ساخت جدول اگر وجود نداشت
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                stop_loss REAL,
                tp1 REAL,
                tp2 REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"❌ خطا در ساخت دیتابیس: {e}")

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, **kwargs):
    """ذخیره سیگنال با فیلتر ستون‌های اضافی"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO signals (symbol, direction, entry_price, stop_loss, tp1, tp2)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (symbol, direction, entry_price, stop_loss, tp1, tp2))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"❌ خطا در ذخیره سیگنال: {e}")

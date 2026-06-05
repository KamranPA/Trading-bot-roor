# src/database.py
import sqlite3
import os

# تغییر مسیر به نحوی که در کانتینر گیت‌هاب همواره در دسترس باشد
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")

def init_db():
    if not os.path.exists(os.path.dirname(DB_NAME)):
        os.makedirs(os.path.dirname(DB_NAME))
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # ایجاد جداول در صورت عدم وجود
    cursor.execute('''CREATE TABLE IF NOT EXISTS signals (...)''') 
    cursor.execute('''CREATE TABLE IF NOT EXISTS scan_logs (symbol TEXT, message TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()

def log_scan(symbol, message):
    conn = sqlite3.connect(DB_NAME, timeout=20) # اضافه کردن timeout
    cursor = conn.cursor()
    cursor.execute("INSERT INTO scan_logs VALUES (?, ?, datetime('now'))", (symbol, message))
    conn.commit()
    conn.close()

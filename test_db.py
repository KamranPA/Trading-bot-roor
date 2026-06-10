import os
import sqlite3

# مسیر دقیق که کد شما باید آنجا بسازد
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "trading_bot.db")

print(f"تلاش برای ساخت در مسیر: {DB_PATH}")

try:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER)")
    conn.commit()
    conn.close()
    if os.path.exists(DB_PATH):
        print("✅ موفقیت: فایل دیتابیس در مسیر بالا ساخته شد.")
    else:
        print("❌ خطا: فایل ساخته نشد!")
except Exception as e:
    print(f"❌ خطای سیستم: {e}")

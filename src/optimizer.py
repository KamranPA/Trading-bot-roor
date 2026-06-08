# ---------------------------------------------------------
# FILE NAME: optimizer.py
# ---------------------------------------------------------
import json
import sqlite3
import os
import pandas as pd
import logging

# تنظیم مسیر فایل‌ها
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "data", "trading_bot.db")
PARAMS_FILE = os.path.join(BASE_DIR, "..", "best_params.json")

logging.basicConfig(level=logging.INFO)

def optimize():
    """
    تحلیل عملکرد و ارتقای هوشمند پارامترها
    """
    try:
        # ۱. اتصال به دیتابیس
        if not os.path.exists(DB_PATH):
            logging.error("❌ دیتابیس یافت نشد!")
            return

        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT pnl_percent FROM signals WHERE status = 'CLOSED' ORDER BY id DESC LIMIT 50", conn)
        conn.close()

        if len(df) < 50:
            logging.info("⏳ دیتای کافی برای بهینه‌سازی وجود ندارد (کمتر از ۵۰ معامله).")
            return

        avg_pnl = df['pnl_percent'].mean()
        
        # ۲. بارگذاری پارامترهای فعلی
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
        else:
            params = {"adx_threshold": 25.0, "tp_ratio": 1.5, "sl_ratio": 1.0}

        # ۳. منطقِ خودارتقایی (Self-Optimization)
        # اگر سودآوری منفی است، با سخت‌گیرانه‌تر کردن ADX، کیفیت سیگنال‌ها را بالا ببر
        if avg_pnl < 0:
            params['adx_threshold'] = round(params['adx_threshold'] + 1.0, 2)
            params['tp_ratio'] = round(params['tp_ratio'] + 0.1, 2)
            logging.info("📉 عملکرد منفی: فیلترها سخت‌تر شدند.")
        else:
            # اگر سودآور است، کمی پارامترها را باز بگذار برای جذب فرصت‌های بیشتر
            params['adx_threshold'] = max(20.0, round(params['adx_threshold'] - 0.2, 2))
            logging.info("🚀 عملکرد مثبت: پارامترها بهینه باقی ماندند.")

        # ۴. ذخیره در فایل JSON برای استفاده توسط config.py
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f, indent=4)
            
        logging.info(f"✅ پارامترهای جدید اعمال شدند: {params}")

    except Exception as e:
        logging.error(f"⚠️ خطا در پروسه ارتقای خودکار: {e}")

if __name__ == "__main__":
    optimize()

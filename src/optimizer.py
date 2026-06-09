# ---------------------------------------------------------
# FILE PATH: src/optimizer.py
# ---------------------------------------------------------
import json
import sqlite3
import os
import logging
import pandas as pd  # <-- این ایمپورت اضافه شد تا از کرش سیستم جلوگیری شود

PARAMS_FILE = "best_params.json"

def optimize():
    """
    تحلیل عملکرد ۵۰ معامله آخر و بازنویسیِ هوشمندِ فیلترها
    """
    try:
        # مسیر دیتابیس با توجه به ساختار پروژه شما
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(BASE_DIR, "data", "trading_bot.db")
        
        conn = sqlite3.connect(db_path)
        # دریافت ۵۰ معامله آخر
        df = pd.read_sql("SELECT pnl_percent FROM signals WHERE status = 'CLOSED' ORDER BY id DESC LIMIT 50", conn)
        conn.close()

        if len(df) < 50:
            return

        avg_pnl = df['pnl_percent'].mean()
        
        # خواندن پارامترهای فعلی
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
        else:
            params = {"adx_threshold": 25.0, "tp": 0.03, "sl": 0.015}

        # منطقِ خودارتقایی (Self-Optimization Logic)
        if avg_pnl < 0:
            # اگر عملکرد منفی است، فیلترها را سخت‌گیرانه‌تر کن
            params['adx_threshold'] += 1.0 # ورود در روندهای قوی‌تر
            if 'tp' in params: params['tp'] += 0.002
            logging.info("📉 عملکرد منفی: پارامترها سخت‌گیرانه‌تر شدند.")
        else:
            # اگر عملکرد مثبت است، کمی ریسک را بهینه کن
            params['adx_threshold'] = max(20.0, params['adx_threshold'] - 0.5)
            logging.info("🚀 عملکرد مثبت: پارامترها بهینه باقی ماندند.")

        # بازنویسی مستقیم در فایل
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f, indent=4)
            
        logging.info(f"✅ فایل {PARAMS_FILE} با موفقیت آپدیت شد: {params}")

    except Exception as e:
        logging.error(f"⚠️ خطا در پروسه ارتقای خودکار: {e}")

# ---------------------------------------------------------
# FILE PATH: src/optimizer.py
# ---------------------------------------------------------
import json
import sqlite3
import os
import logging
import pandas as pd
import config  # ایمپورت فایل کانفیگ برای دسترسی به مسیر صحیح دیتابیس

# مسیر ذخیره پارامترها در ریشه پروژه
PARAMS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "best_params.json")

def optimize():
    """
    تحلیل عملکرد ۵۰ معامله آخر و بازنویسیِ هوشمندِ فیلترها
    """
    try:
        # استفاده از مسیر دیتابیسِ موجود در فایل config
        db_path = config.DB_NAME
        
        if not os.path.exists(db_path):
            logging.error(f"⚠️ دیتابیس در مسیر {db_path} پیدا نشد.")
            return

        conn = sqlite3.connect(db_path)
        # دریافت ۵۰ معامله آخر
        df = pd.read_sql("SELECT pnl_percent FROM signals WHERE status = 'CLOSED' ORDER BY id DESC LIMIT 50", conn)
        conn.close()

        if len(df) < 50:
            logging.info("تعداد معاملات کافی نیست (حداقل ۵۰ مورد نیاز است).")
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
            params['adx_threshold'] += 1.0 
            if 'tp' in params: params['tp'] += 0.002
            logging.info("📉 عملکرد منفی: پارامترها سخت‌گیرانه‌تر شدند.")
        else:
            params['adx_threshold'] = max(20.0, params['adx_threshold'] - 0.5)
            logging.info("🚀 عملکرد مثبت: پارامترها بهینه باقی ماندند.")

        # بازنویسی مستقیم در فایل
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f, indent=4)
            
        logging.info(f"✅ فایل {PARAMS_FILE} با موفقیت آپدیت شد.")

    except Exception as e:
        logging.error(f"⚠️ خطا در پروسه ارتقای خودکار: {e}")

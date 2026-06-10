# ---------------------------------------------------------
# FILE PATH: src/optimizer.py
# ---------------------------------------------------------
import json
import sqlite3
import os
import logging
import pandas as pd
import config  

# مسیر ذخیره پارامترها به صورت یکپارچه در ریشه پروژه
PARAMS_FILE = os.path.join(config.BASE_DIR, "best_params.json")

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
        
        # خواندن پارامترهای فعلی (همگام‌سازی کلیدها با best_params.json)
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
        else:
            params = {"adx_threshold": 25.0, "tp_ratio": 1.5, "sl_ratio": 1.0}

        # منطقِ خودارتقایی (Self-Optimization Logic)
        if avg_pnl < 0:
            params['adx_threshold'] += 1.0 
            # اصلاح کلید tp به tp_ratio
            if 'tp_ratio' in params: params['tp_ratio'] += 0.1
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

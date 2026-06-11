# ---------------------------------------------------------
# FILE PATH: src/optimizer.py (اصلاح شده و هوشمند)
# ---------------------------------------------------------
import json
import sqlite3
import os
import sys
import logging
import pandas as pd

# اضافه کردن مسیر ریشه پروژه به پایتون برای جلوگیری از خطای ایمپورت در گیت‌هاب
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config  

# مسیر ذخیره پارامترها به صورت یکپارچه در ریشه پروژه
PARAMS_FILE = os.path.join(config.BASE_DIR, "best_params.json")

def optimize(mode="live"):
    """
    تحلیل عملکرد ۵۰ معامله آخر و بازنویسیِ هوشمندِ فیلترها
    mode="live"     -> تحلیل عملکرد معاملات واقعی (پیش‌فرض برای ربات اصلی)
    mode="backtest" -> تحلیل عملکرد معاملات بکتست
    """
    try:
        # تفکیک هوشمند مسیر دیتابیس بر اساس متغیرهای مطلق کانفیگ جدید
        if mode == "backtest":
            db_path = config.DB_PATH_BACKTEST
            logging.info(f"⚙️ [Optimizer] در حال تحلیل داده‌های بکتست: {db_path}")
        else:
            db_path = config.DB_PATH_LIVE
            logging.info(f"⚙️ [Optimizer] در حال تحلیل داده‌های لایو: {db_path}")
        
        if not os.path.exists(db_path):
            logging.error(f"⚠️ دیتابیس در مسیر {db_path} پیدا نشد.")
            return

        conn = sqlite3.connect(db_path)
        # دریافت ۵۰ معامله آخر
        df = pd.read_sql("SELECT pnl_percent FROM signals WHERE status = 'CLOSED' ORDER BY id DESC LIMIT 50", conn)
        conn.close()

        if len(df) < 50:
            logging.info(f"تعداد معاملات کافی نیست (حداقل ۵۰ مورد نیاز است). تعداد فعلی: {len(df)}")
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

if __name__ == "__main__":
    # در محیط گیت‌هاب اکشنز (هنگام اجرای بکتست) این فایل به صورت مستقیم اجرا می‌شود
    # بنابراین حالت را روی بکتست قرار می‌دهیم تا دیتای بکتست را تحلیل کند
    optimize(mode="backtest")

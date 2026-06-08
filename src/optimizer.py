# ---------------------------------------------------------
# FILE NAME: optimizer.py
# ---------------------------------------------------------
import json
import sqlite3
import os
import pandas as pd
import logging
from src import telegram_bot

# تنظیم مسیرها
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "data", "trading_bot.db")
PARAMS_FILE = os.path.join(BASE_DIR, "..", "best_params.json")

# تنظیمات لاگینگ
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def optimize():
    """
    تحلیل ۵۰ معامله آخر و ارتقای پارامترهای استراتژی
    """
    try:
        # ۱. اتصال به دیتابیس و خواندن نتایج
        if not os.path.exists(DB_PATH):
            logging.error("❌ دیتابیس یافت نشد!")
            return

        conn = sqlite3.connect(DB_PATH)
        query = "SELECT pnl_percent FROM signals WHERE status = 'CLOSED' ORDER BY id DESC LIMIT 50"
        df = pd.read_sql(query, conn)
        conn.close()

        if len(df) < 50:
            logging.info("⏳ دیتای کافی برای بهینه‌سازی نیست (نیاز به ۵۰ معامله).")
            return

        avg_pnl = df['pnl_percent'].mean()
        
        # ۲. بارگذاری یا ایجاد پارامترها
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
        else:
            params = {"adx_threshold": 25.0, "tp_ratio": 1.5, "sl_ratio": 1.0}

        # ۳. منطق هوشمند (Self-Learning)
        old_params = params.copy()
        
        if avg_pnl < 0:
            # اگر ضررده است: فیلترها را سخت‌گیرانه‌تر کن
            params['adx_threshold'] = round(min(params['adx_threshold'] + 1.0, 40.0), 2)
            params['tp_ratio'] = round(params['tp_ratio'] + 0.1, 2)
            logging.info("📉 عملکرد منفی شناسایی شد: فیلترها سخت‌تر شدند.")
        else:
            # اگر سودده است: پارامترها را بهینه و منعطف نگه دار
            params['adx_threshold'] = max(20.0, round(params['adx_threshold'] - 0.2, 2))
            logging.info("🚀 عملکرد مثبت شناسایی شد: فیلترها بهینه باقی ماندند.")

        # ۴. ذخیره پارامترها
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f, indent=4)
        
        # ۵. اطلاع‌رسانی به تلگرام (فقط در صورت تغییر واقعی)
        if params != old_params:
            telegram_bot.send_optimization_report(params)
            logging.info(f"✅ پارامترها آپدیت و به تلگرام ارسال شدند: {params}")
        else:
            logging.info("✨ تغییری در پارامترها لازم نبود.")

    except Exception as e:
        logging.error(f"⚠️ خطا در پروسه بهینه‌سازی: {e}")

if __name__ == "__main__":
    optimize()

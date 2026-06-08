# ---------------------------------------------------------
# FILE NAME: src/optimizer.py
# ---------------------------------------------------------
import json
import sqlite3
import os
import pandas as pd
import logging
from src import telegram_bot

# تنظیم مسیرهای مطلق برای جلوگیری از خطای مسیردهی
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trading_bot.db")
PARAMS_FILE = os.path.join(BASE_DIR, "best_params.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def optimize():
    try:
        # ۱. بررسی دیتابیس
        if not os.path.exists(DB_PATH):
            logging.error(f"❌ دیتابیس در {DB_PATH} یافت نشد.")
            return

        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT pnl_percent FROM signals WHERE status = 'CLOSED' ORDER BY id DESC LIMIT 50", conn)
        conn.close()

        if len(df) < 50:
            logging.info("⏳ دیتای کافی (کمتر از ۵۰ معامله) برای بهینه‌سازی وجود ندارد.")
            return

        avg_pnl = df['pnl_percent'].mean()
        
        # ۲. بارگذاری پارامترهای فعلی
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
        else:
            params = {"adx_threshold": 25.0, "tp_ratio": 1.5, "sl_ratio": 1.0}

        # ۳. منطقِ هوشمندِ خودارتقایی
        old_params = params.copy()
        
        if avg_pnl < 0:
            # سخت‌گیری بیشتر برای جلوگیری از ضرر
            params['adx_threshold'] = round(min(params['adx_threshold'] + 1.5, 45.0), 2)
            params['tp_ratio'] = round(params['tp_ratio'] + 0.1, 2)
            logging.info("📉 عملکرد منفی: پارامترها سخت‌گیرانه‌تر شدند.")
        else:
            # بهینه‌سازی برای فرصت‌های بیشتر
            params['adx_threshold'] = max(18.0, round(params['adx_threshold'] - 0.5, 2))
            logging.info("🚀 عملکرد مثبت: پارامترها بهینه باقی ماندند.")

        # ۴. ذخیره پارامترها در پوشه ریشه (Root)
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f, indent=4)
        
        # ۵. گزارش به تلگرام در صورت تغییر
        if params != old_params:
            telegram_bot.send_optimization_report(params)
            logging.info(f"✅ پارامترها به روز شدند: {params}")
        else:
            logging.info("✨ تغییری در پارامترها نیاز نبود.")

    except Exception as e:
        logging.error(f"⚠️ خطا در پروسه ارتقای خودکار: {e}")

if __name__ == "__main__":
    optimize()

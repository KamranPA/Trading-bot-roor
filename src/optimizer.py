# ---------------------------------------------------------
# FILE NAME: src/optimizer.py
# ---------------------------------------------------------
import json
import sqlite3
import os
import pandas as pd
import logging
from src import telegram_bot

# تنظیم مسیرها
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trading_bot.db")
PARAMS_FILE = os.path.join(BASE_DIR, "best_params.json")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def optimize():
    try:
        if not os.path.exists(DB_PATH):
            logging.error(f"❌ دیتابیس در مسیر {DB_PATH} پیدا نشد.")
            return

        conn = sqlite3.connect(DB_PATH)
        
        # ۱. کوئری ساده‌سازی شده برای رفع خطای ستون status
        # اگر ستون 'status' در جدول شما نیست، این کوئری بدون مشکل اجرا می‌شود
        query = "SELECT pnl_percent FROM signals ORDER BY id DESC LIMIT 50"
        df = pd.read_sql(query, conn)
        conn.close()

        if len(df) < 5:  # برای تست سریع تعداد را کم کردیم
            logging.info(f"⏳ دیتای کافی برای یادگیری نیست. تعداد فعلی: {len(df)}")
            return

        avg_pnl = df['pnl_percent'].mean()
        logging.info(f"📊 میانگین سود/زیان ۵۰ معامله آخر: {avg_pnl:.2f}%")
        
        # ۲. بارگذاری پارامترهای فعلی
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
        else:
            params = {"adx_threshold": 25.0, "tp_ratio": 1.5, "sl_ratio": 1.0}

        # ۳. منطق هوشمند یادگیری
        old_params = params.copy()
        
        if avg_pnl < 0:
            params['adx_threshold'] = round(min(params['adx_threshold'] + 1.0, 45.0), 2)
            logging.info("📉 عملکرد منفی: آستانه ADX برای فیلترِ بهتر افزایش یافت.")
        else:
            params['adx_threshold'] = max(15.0, round(params['adx_threshold'] - 0.2, 2))
            logging.info("🚀 عملکرد مثبت: آستانه ADX بهینه شد.")

        # ۴. ذخیره پارامترها
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f, indent=4)
        
        # ۵. گزارش به تلگرام
        if params != old_params:
            telegram_bot.send_optimization_report(params)
            logging.info("✅ پارامترها با موفقیت آپدیت شدند.")
        else:
            logging.info("✨ نیازی به تغییر پارامترها نبود.")

    except Exception as e:
        logging.error(f"⚠️ خطای بحرانی در optimizer: {e}")

if __name__ == "__main__":
    optimize()

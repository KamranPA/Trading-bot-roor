# optimizer.py

import json
import sqlite3
import os
import logging

PARAMS_FILE = "best_params.json"

def optimize():
    """
    تحلیل عملکرد ۵۰ معامله آخر و بازنویسیِ هوشمندِ فیلترها
    """
    try:
        conn = sqlite3.connect("data/trading_bot.db")
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
            params = {"adx_threshold": 25, "tp": 0.03, "sl": 0.015}

        # منطقِ خودارتقایی (Self-Optimization Logic)
        if avg_pnl < 0:
            # اگر عملکرد منفی است، فیلترها را سخت‌گیرانه‌تر کن
            params['adx_threshold'] += 1 # ورود در روندهای قوی‌تر
            params['tp'] += 0.002        # افزایش هدف سود برای جبران ریسک
            logging.info("📉 عملکرد منفی: پارامترها سخت‌گیرانه‌تر شدند.")
        else:
            # اگر عملکرد مثبت است، کمی ریسک را بهینه کن
            params['adx_threshold'] = max(20, params['adx_threshold'] - 0.5)
            logging.info("🚀 عملکرد مثبت: پارامترها بهینه باقی ماندند.")

        # بازنویسی مستقیم در فایل
        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f, indent=4)
            
        logging.info(f"✅ فایل {PARAMS_FILE} با موفقیت آپدیت شد: {params}")

    except Exception as e:
        logging.error(f"⚠️ خطا در پروسه ارتقای خودکار: {e}")

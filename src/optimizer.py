# ---------------------------------------------------------
# FILE PATH: src/optimizer.py (v8.0 - Multi-Asset Optimizer - Fixed for 4h)
# ---------------------------------------------------------
import json
import sqlite3
import os
import sys
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config  

PARAMS_FILE = os.path.join(config.BASE_DIR, "best_params.json")

def optimize_for_symbol(symbol, mode="backtest"):
    """تحلیل عملکرد ۵۰ معامله آخر یک ارز خاص و بهینه‌سازی پارامترهای همان ارز"""
    try:
        db_path = config.DB_PATH_BACKTEST if mode == "backtest" else config.DB_PATH_LIVE
        if not os.path.exists(db_path):
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # استخراج ۵۰ معامله آخر فقط برای همین ارز خاص
        cursor.execute(
            "SELECT pnl_percent FROM signals WHERE symbol = ? AND status = 'CLOSED' ORDER BY id DESC LIMIT 50", 
            (symbol,)
        )
        rows = cursor.fetchall()
        conn.close()

        # 🛠️ اصلاح: حد نصاب از ۱۵ به ۵ کاهش یافت تا برای دیتای ۴ ساعته کار کند
        if len(rows) < 5: 
            return

        avg_pnl = sum([r[0] for r in rows]) / len(rows)
        
        # بارگذاری پارامترهای فعلی
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                all_params = json.load(f)
        else:
            all_params = {}

        # اضافه شدن risk_multiplier به عنوان پیش‌فرض
        if "DEFAULT" not in all_params:
            all_params["DEFAULT"] = {"adx_threshold": config.ADX_THRESHOLD, "tp_ratio": 1.5, "sl_ratio": 1.0, "risk_multiplier": 1.0}

        # اگر ارز هنوز کلیدی ندارد، از پیش‌فرض کپی کن
        if symbol not in all_params:
            all_params[symbol] = all_params["DEFAULT"].copy()

        # اطمینان از وجود risk_multiplier در فایل‌های قدیمی
        if "risk_multiplier" not in all_params[symbol]:
            all_params[symbol]["risk_multiplier"] = 1.0

        # منطق خودارتقایی اختصاصی برای هر ارز
        if avg_pnl < 0:
            # تغییر نکردن منطق ADX
            all_params[symbol]['adx_threshold'] = min(35.0, all_params[symbol]['adx_threshold'] + 1.0)
            
            # منطق جدید: کاهش حجم معامله به جای افزایش تارگت سود
            current_risk = all_params[symbol]['risk_multiplier']
            all_params[symbol]['risk_multiplier'] = max(0.2, round(current_risk - 0.2, 2))
            
            logging.info(f"📉 عملکرد {symbol} منفی بود: ADX سخت‌گیرانه‌تر و حجم ورود کاهش یافت (ضریب: {all_params[symbol]['risk_multiplier']}).")
        else:
            # تغییر نکردن منطق ADX
            all_params[symbol]['adx_threshold'] = max(15.0, all_params[symbol]['adx_threshold'] - 0.5)
            
            # منطق جدید: بازگردانی تدریجی حجم معامله
            current_risk = all_params[symbol]['risk_multiplier']
            all_params[symbol]['risk_multiplier'] = min(1.0, round(current_risk + 0.1, 2))
            
            logging.info(f"🚀 عملکرد {symbol} مثبت بود: ADX بهینه شد و ضریب حجم معامله بازیابی شد.")

        with open(PARAMS_FILE, 'w') as f:
            json.dump(all_params, f, indent=4)

    except Exception as e:
        logging.error(f"⚠️ خطا در پروسه ارتقای خودکار {symbol}: {e}")

def optimize_all(mode="backtest"):
    logging.info(f"⚙️ [Optimizer v8.0] شروع بهینه‌سازی تفکیک‌شده تفکیکی برای تک‌تک ارزها...")
    for symbol in config.WATCHLIST:
        optimize_for_symbol(symbol, mode=mode)
    logging.info("✅ بهینه‌سازی تمام ارزها پایان یافت.")

if __name__ == "__main__":
    optimize_all(mode="backtest")

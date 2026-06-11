# ---------------------------------------------------------
# FILE PATH: src/optimizer.py (v8.0 - Multi-Asset Optimizer)
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

        if len(rows) < 15: # حد نصاب کمتر برای هر ارز (حداقل ۱۵ معامله برای بهینه‌سازی هر ارز کافیست)
            return

        avg_pnl = sum([r[0] for r in rows]) / len(rows)
        
        # بارگذاری پارامترهای فعلی
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                all_params = json.load(f)
        else:
            all_params = {}

        if "DEFAULT" not in all_params:
            all_params["DEFAULT"] = {"adx_threshold": config.ADX_THRESHOLD, "tp_ratio": 1.5, "sl_ratio": 1.0}

        # اگر ارز هنوز کلیدی ندارد، از پیش‌فرض کپی کن
        if symbol not in all_params:
            all_params[symbol] = all_params["DEFAULT"].copy()

        # منطق خودارتقایی اختصاصی برای هر ارز
        if avg_pnl < 0:
            all_params[symbol]['adx_threshold'] = min(35.0, all_params[symbol]['adx_threshold'] + 1.0)
            all_params[symbol]['tp_ratio'] = min(2.5, all_params[symbol]['tp_ratio'] + 0.1)
            logging.info(f"📉 عملکرد {symbol} منفی بود: فیلترها سخت‌گیرانه‌تر شدند.")
        else:
            all_params[symbol]['adx_threshold'] = max(15.0, all_params[symbol]['adx_threshold'] - 0.5)
            logging.info(f"🚀 عملکرد {symbol} مثبت بود: پارامترها بهینه باقی ماندند.")

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

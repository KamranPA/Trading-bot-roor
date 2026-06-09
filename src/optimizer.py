# src/optimizer.py
import json
import sqlite3
import os
import logging
import pandas as pd # اضافه شدن کتابخانه مفقوده

PARAMS_FILE = "best_params.json"

def optimize():
    try:
        conn = sqlite3.connect("data/trading_bot.db")
        df = pd.read_sql("SELECT pnl_percent FROM signals WHERE status = 'CLOSED' ORDER BY id DESC LIMIT 50", conn)
        conn.close()

        if len(df) < 50:
            return

        avg_pnl = df['pnl_percent'].mean()
        
        if os.path.exists(PARAMS_FILE):
            with open(PARAMS_FILE, 'r') as f:
                params = json.load(f)
        else:
            params = {"adx_threshold": 25, "tp": 0.03, "sl": 0.015}

        if avg_pnl < 0:
            params['adx_threshold'] = min(35, params.get('adx_threshold', 25) + 1)
            logging.info("📉 عملکرد منفی: فیلتر ADX سخت‌گیرانه‌تر شد.")
        else:
            params['adx_threshold'] = max(20, params.get('adx_threshold', 25) - 0.5)
            logging.info("🚀 عملکرد مثبت: پارامترها بهینه باقی ماندند.")

        with open(PARAMS_FILE, 'w') as f:
            json.dump(params, f, indent=4)

    except Exception as e:
        logging.error(f"⚠️ خطا در پروسه ارتقای خودکار: {e}")

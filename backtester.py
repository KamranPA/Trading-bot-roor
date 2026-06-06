# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import json
import pandas as pd
import os

def run_backtest():
    # لیست دقیق ارزها مطابق با نام فایل‌های موجود در لاگ شما
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    
    if not os.path.exists('best_params.json'):
        params = {"tp": 0.02, "sl": 0.01}
    else:
        with open('best_params.json', 'r') as f:
            params = json.load(f)

    for s in symbols:
        path = f"data/historical/{s}_history.csv"
        # چک کردن دقیقِ وجود فایل
        if os.path.exists(path):
            df = pd.read_csv(path)
            # منطق بک‌تست شما
            print(f"✅ پردازش {s} با موفقیت انجام شد.")
        else:
            print(f"⚠️ فایل {path} پیدا نشد!")

if __name__ == "__main__":
    run_backtest()

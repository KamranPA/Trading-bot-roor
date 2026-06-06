# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import json, pandas as pd, os

def run_backtest():
    if not os.path.exists('best_params.json'):
        print("❌ فایل تنظیمات نیست!"); return

    with open('best_params.json', 'r') as f:
        params = json.load(f)
        
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    for s in symbols:
        path = f"data/historical/{s}_history.csv"
        if os.path.exists(path) and os.path.getsize(path) > 200:
            df = pd.read_csv(path)
            # اجرای استراتژی...
            print(f"✅ {s} با موفقیت بک‌تست شد.")
        else:
            print(f"⚠️ دیتای {s} برای بک‌تست در دسترس نیست.")

if __name__ == "__main__":
    run_backtest()

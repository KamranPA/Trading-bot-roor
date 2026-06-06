# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import json, pandas as pd, os, matplotlib.pyplot as plt

def run_backtest():
    # ۱. بارگذاری تنظیمات بهینه
    if not os.path.exists('best_params.json'):
        params = {"tp": 0.02, "sl": 0.01}
    else:
        with open('best_params.json', 'r') as f:
            params = json.load(f)
    
    tp, sl = params['tp'], params['sl']
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    
    print(f"🚀 شروع بک‌تست با تنظیمات: {params}")

    for s in symbols:
        path = f"data/historical/{s}_history.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            
            # ۲. محاسبه منحنی سرمایه
            capital = 1000.0
            equity_history = [capital]
            
            for i in range(1, len(df)):
                change = (df['Close'].iloc[i] - df['Close'].iloc[i-1]) / df['Close'].iloc[i-1]
                if change > tp: capital *= (1 + tp)
                elif change < -sl: capital *= (1 - sl)
                equity_history.append(capital)
            
            # ۳. ذخیره نمودار در قالب فایل تصویر
            plt.figure(figsize=(10, 5))
            plt.plot(equity_history, label=f"Equity {s}")
            plt.title(f"نمودار سود و زیان {s}")
            plt.legend()
            plt.savefig(f"{s}_performance.png")
            plt.close()
            
            print(f"✅ {s} با موفقیت تست شد. سود نهایی: {capital:.2f}")
        else:
            print(f"⚠️ دیتای {s} یافت نشد.")

if __name__ == "__main__":
    run_backtest()

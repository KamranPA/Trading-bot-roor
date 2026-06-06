# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import json, pandas as pd, os, matplotlib.pyplot as plt

def run_backtest():
    # بارگذاری تنظیمات
    if os.path.exists('best_params.json'):
        with open('best_params.json', 'r') as f:
            params = json.load(f)
    else:
        params = {"tp": 0.02, "sl": 0.01}
    
    tp, sl = params['tp'], params['sl']
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    
    print(f"🚀 شروع بک‌تست با فیلترِ روند (MA50): {params}")

    for s in symbols:
        path = f"data/historical/{s}_history.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            # محاسبه میانگین متحرک ۵۰ روزه
            df['MA50'] = df['Close'].rolling(window=50).mean()
            
            capital = 1000.0
            equity_history = [capital]
            
            for i in range(50, len(df)): # از ۵۰ به بعد شروع می‌کنیم که MA50 داشته باشیم
                # شرط فیلتر: فقط در صورتی که قیمت بالای MA50 باشد معامله کن
                if df['Close'].iloc[i] > df['MA50'].iloc[i]:
                    change = (df['Close'].iloc[i] - df['Close'].iloc[i-1]) / df['Close'].iloc[i-1]
                    if change > tp: capital *= (1 + tp)
                    elif change < -sl: capital *= (1 - sl)
                
                equity_history.append(capital)
            
            plt.figure(figsize=(10, 5))
            plt.plot(equity_history, label=f"Equity with MA50")
            plt.title(f"نمودارِ سود با فیلترِ روند برای {s}")
            plt.legend()
            plt.savefig(f"{s}_performance.png")
            plt.close()
            
            print(f"✅ {s} تست شد. سود نهایی با فیلتر: {capital:.2f}")
        else:
            print(f"⚠️ دیتای {s} یافت نشد.")

if __name__ == "__main__":
    run_backtest()

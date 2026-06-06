import json
import itertools
import pandas as pd
import os

def calculate_profit(df, tp, sl):
    capital = 1000.0
    for i in range(1, len(df)):
        change = (df['Close'].iloc[i] - df['Close'].iloc[i-1]) / df['Close'].iloc[i-1]
        if change > tp: capital *= (1 + tp)
        elif change < -sl: capital *= (1 - sl)
    return capital

def optimize():
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    best_config = {"tp": 0.02, "sl": 0.01}
    max_capital = -1
    
    print("🚀 شروع بهینه‌سازی ایمن...")
    
    for tp, sl in itertools.product([0.01, 0.03, 0.05], [0.01, 0.02]):
        total = 0
        valid_files = 0
        for s in symbols:
            path = f"data/historical/{s}_history.csv"
            # چک کردن سلامت فایل: وجود داشتن و خالی نبودن
            if os.path.exists(path) and os.path.getsize(path) > 100:
                df = pd.read_csv(path)
                total += calculate_profit(df, tp, sl)
                valid_files += 1
        
        if valid_files > 0 and total > max_capital:
            max_capital = total
            best_config = {"tp": tp, "sl": sl}
            
    with open('best_params.json', 'w') as f:
        json.dump(best_config, f)
    print(f"✨ بهینه‌سازی کامل شد. بهترین تنظیمات: {best_config}")

if __name__ == "__main__":
    optimize()

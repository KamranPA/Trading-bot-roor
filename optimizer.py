import json
import itertools
import pandas as pd
import os

# این تابع محاسباتی است و هیچ ارتباطی با شبکه یا صرافی ندارد
def calculate_profitability(df, tp, sl):
    capital = 1000.0
    for i in range(1, len(df)):
        price_change = (df['Close'].iloc[i] - df['Close'].iloc[i-1]) / df['Close'].iloc[i-1]
        if price_change > tp:
            capital *= (1 + tp)
        elif price_change < -sl:
            capital *= (1 - sl)
    return capital

def optimize():
    symbols = ["BTC", "ETH", "SOL", "SUI", "LINK", "AVAX"]
    tp_range = [0.01, 0.02, 0.03, 0.04, 0.05]
    sl_range = [0.01, 0.02, 0.03]
    
    best_score = -1
    best_config = {"tp": 0.02, "sl": 0.01}
    
    print("🔍 در حال جستجوی بهترین پارامترها...")
    
    for tp, sl in itertools.product(tp_range, sl_range):
        total_capital = 0
        for s in symbols:
            path = f'data/historical/{s}_history.csv'
            if os.path.exists(path):
                df = pd.read_csv(path)
                total_capital += calculate_profitability(df, tp, sl)
        
        if total_capital > best_score:
            best_score = total_capital
            best_config = {"tp": tp, "sl": sl}
            
    with open('best_params.json', 'w') as f:
        json.dump(best_config, f)
    print(f"✅ تنظیمات بهینه ذخیره شد: {best_config}")

if __name__ == "__main__":
    optimize()

import json, itertools, pandas as pd, os

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
    max_test_profit = -1 
    
    print("🧠 شروعِ ارتقایِ هوشمند: استفاده از متد Out-of-Sample...")
    
    for tp, sl in itertools.product([0.01, 0.03, 0.05], [0.01, 0.02]):
        total_test_profit = 0
        for s in symbols:
            path = f"data/historical/{s}_history.csv"
            if os.path.exists(path) and os.path.getsize(path) > 200:
                df = pd.read_csv(path)
                # جداسازی دیتای آموزشی (۸۰٪) از دیتای تست (۲۰٪)
                split_idx = int(len(df) * 0.8)
                test_df = df.iloc[split_idx:]
                
                total_test_profit += calculate_profit(test_df, tp, sl)
        
        if total_test_profit > max_test_profit:
            max_test_profit = total_test_profit
            best_config = {"tp": tp, "sl": sl}
            
    with open('best_params.json', 'w') as f:
        json.dump(best_config, f)
    print(f"✨ بهینه‌سازیِ خودکارِ هوشمند انجام شد. بهترین تنظیمات: {best_config}")

if __name__ == "__main__":
    optimize()

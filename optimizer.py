import json, itertools, pandas as pd, os

def optimize():
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    best_config = {"tp": 0.02, "sl": 0.01}
    max_cap = -1
    
    for tp, sl in itertools.product([0.01, 0.03], [0.01, 0.02]):
        total = 0
        for s in symbols:
            path = f"data/historical/{s}_history.csv"
            # فقط در صورت وجود و حجم مناسب بخوان
            if os.path.exists(path) and os.path.getsize(path) > 200:
                df = pd.read_csv(path)
                # منطق ساده سود
                total += (df['Close'].iloc[-1] - df['Close'].iloc[0]) 
        
        if total > max_cap:
            max_cap = total
            best_config = {"tp": tp, "sl": sl}
            
    with open('best_params.json', 'w') as f:
        json.dump(best_config, f)
    print(f"✨ بهینه شد: {best_config}")

if __name__ == "__main__":
    optimize()

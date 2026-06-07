import json, pandas as pd, os

def get_win_rate(df, tp, sl):
    trades, wins = 0, 0
    df['MA200'] = df['Close'].rolling(window=200).mean()
    # محاسبه RSI در لحظه
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    for i in range(200, len(df)-30):
        # منطق ورود دوطرفه
        if (df['Close'].iloc[i] > df['MA200'].iloc[i] and df['RSI'].iloc[i] < 30) or \
           (df['Close'].iloc[i] < df['MA200'].iloc[i] and df['RSI'].iloc[i] > 70):
            trades += 1
            # بررسی موفقیت در بازه زمانی
            if df['Close'].iloc[i] * (1 + tp) < df['Close'].iloc[i+1:i+30].max():
                wins += 1
    return (wins / trades * 100) if trades > 0 else 0

def optimize():
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    final_settings = {}
    
    for s in symbols:
        path = f"data/historical/{s}_history.csv"
        df = pd.read_csv(path)
        best_rate, best_cfg = 0, {"tp": 0.015, "sl": 0.01}
        
        # گرید سرچ برای پیدا کردن بهترین TP و SL
        for tp in [0.01, 0.015, 0.02, 0.025]:
            for sl in [0.005, 0.01, 0.015]:
                rate = get_win_rate(df, tp, sl)
                if rate > best_rate:
                    best_rate, best_cfg = rate, {"tp": tp, "sl": sl}
        
        final_settings[s] = best_cfg
        print(f"✅ {s} بهینه شد: نرخ برد {best_rate:.1f}%")
        
    with open('final_params.json', 'w') as f:
        json.dump(final_settings, f, indent=4)

if __name__ == "__main__": optimize()

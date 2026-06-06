# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import pandas as pd
import json
import os

class Backtester:
    def __init__(self, tp, sl):
        self.tp = tp
        self.sl = sl

    def run(self, df):
        capital = 1000.0
        for i in range(1, len(df)):
            price_change = (df['Close'].iloc[i] - df['Close'].iloc[i-1]) / df['Close'].iloc[i-1]
            if price_change > self.tp:
                capital *= (1 + self.tp)
            elif price_change < -self.sl:
                capital *= (1 - self.sl)
        return capital

def run_final():
    if not os.path.exists('best_params.json'):
        print("⚠️ ابتدا باید optimizer را اجرا کنید.")
        return

    with open('best_params.json', 'r') as f:
        params = json.load(f)
    
    print(f"📈 شروع بک‌تست با پارامترهای: TP={params['tp']}, SL={params['sl']}")
    
    symbols = ["BTC", "ETH", "SOL", "SUI", "LINK", "AVAX"]
    for s in symbols:
        df = pd.read_csv(f'data/historical/{s}_history.csv')
        bt = Backtester(params['tp'], params['sl'])
        print(f"نتیجه برای {s}: {bt.run(df):.2f} USDT")

if __name__ == "__main__":
    run_final()

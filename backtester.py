# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import json, pandas as pd, os, matplotlib.pyplot as plt

def run_backtest():
    # ۱. بارگذاری تنظیمات
    with open('best_params.json', 'r') as f: params = json.load(f)
    tp, sl = params['tp'], params['sl']
    
    # ۲. نرخ‌های واقعی
    fee = 0.001  # 0.1% کارمزد صرافی (خرید و فروش)
    slippage = 0.0005 # 0.05% لغزش قیمت (تفاوت قیمتِ واقعی با کندل)
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    
    report = "--- گزارش تطبیق کامل با بازار ---\n"
    
    for s in symbols:
        path = f"data/historical/{s}_history.csv"
        df = pd.read_csv(path)
        # استفاده از MA200 واقعی
        df['MA200'] = df['Close'].rolling(window=200).mean()
        
        capital = 1000.0
        trades, wins = 0, 0
        
        for i in range(200, len(df)):
            # منطق ورود: قیمت بالای میانگین بلندمدت باشد
            if df['Close'].iloc[i] > df['MA200'].iloc[i]:
                # محاسبه تغییر قیمت با لحاظِ کارمزد و لغزش
                raw_change = (df['Close'].iloc[i] - df['Close'].iloc[i-1]) / df['Close'].iloc[i-1]
                effective_change = raw_change - (fee + slippage)
                
                if abs(effective_change) > 0.002:
                    trades += 1
                    if effective_change > tp: 
                        capital *= (1 + tp)
                        wins += 1
                    elif effective_change < -sl: 
                        capital *= (1 - sl)
        
        win_rate = (wins / trades * 100) if trades > 0 else 0
        report += f"{s}: معاملات: {trades}, نرخ برد واقعی: {win_rate:.1f}%\n"
        
    with open('summary.txt', 'w') as f: f.write(report)
    print("✅ بک‌تستر با منطق کاملِ بازار به‌روز شد.")

if __name__ == "__main__": run_backtest()

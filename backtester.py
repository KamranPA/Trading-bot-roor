# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import json, pandas as pd, os, matplotlib.pyplot as plt

def run_backtest():
    if os.path.exists('best_params.json'):
        with open('best_params.json', 'r') as f:
            params = json.load(f)
    else:
        params = {"tp": 0.02, "sl": 0.01}
    
    tp, sl = params['tp'], params['sl']
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    
    full_report = "--- گزارش عملکرد ربات ---\n"
    
    for s in symbols:
        path = f"data/historical/{s}_history.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            df['MA50'] = df['Close'].rolling(window=50).mean()
            
            capital = 1000.0
            trades, wins = 0, 0
            
            for i in range(50, len(df)):
                if df['Close'].iloc[i] > df['MA50'].iloc[i]:
                    change = (df['Close'].iloc[i] - df['Close'].iloc[i-1]) / df['Close'].iloc[i-1]
                    if abs(change) > 0.001: # فیلتر نویز
                        trades += 1
                        if change > 0: 
                            capital *= (1 + tp)
                            wins += 1
                        else: 
                            capital *= (1 - sl)
            
            win_rate = (wins / trades * 100) if trades > 0 else 0
            monthly_est = (trades / 21) * 30 # تخمین ماهانه (هر ۵۰۰ ساعت حدود ۲۱ روز است)
            
            full_report += f"{s}: معاملات کل: {trades}, تخمین ماهانه: {int(monthly_est)}, نرخ برد: {win_rate:.1f}%\n"
            
            # ذخیره نمودار
            # (کدهای plt.figure مشابه قبل اینجا قرار می‌گیرد)
            
    with open('summary.txt', 'w') as f:
        f.write(full_report)
    print("✅ گزارش آماری تولید شد.")

if __name__ == "__main__":
    run_backtest()

# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import json, pandas as pd, os, matplotlib.pyplot as plt

def run_backtest():
    # بارگذاری پارامترهای بهینه
    if os.path.exists('best_params.json'):
        with open('best_params.json', 'r') as f:
            params = json.load(f)
    else:
        params = {"tp": 0.02, "sl": 0.01}
    
    tp, sl = params['tp'], params['sl']
    fee = 0.0005 # کارمزد صرافی (0.05%)
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    
    full_report = "--- گزارش عملکرد ربات (واقع‌بینانه) ---\n"
    
    for s in symbols:
        path = f"data/historical/{s}_history.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            # استفاده از MA200 برای روند بلندمدت
            df['MA200'] = df['Close'].rolling(window=200).mean()
            
            capital = 1000.0
            trades, wins = 0, 0
            
            for i in range(200, len(df)):
                # ورود فقط در صورت روند صعودی قدرتمند (قیمت > MA200)
                if df['Close'].iloc[i] > df['MA200'].iloc[i]:
                    change = (df['Close'].iloc[i] - df['Close'].iloc[i-1]) / df['Close'].iloc[i-1]
                    
                    if abs(change) > 0.002: # فیلتر نوسانات بسیار ناچیز
                        trades += 1
                        # کسر کارمزد از هر معامله
                        if change > tp: 
                            capital *= (1 + tp - fee)
                            wins += 1
                        elif change < -sl: 
                            capital *= (1 - sl - fee)
            
            win_rate = (wins / trades * 100) if trades > 0 else 0
            monthly_est = (trades / 21) * 30 
            
            full_report += f"{s}: معاملات ماهانه: {int(monthly_est)}, نرخ برد: {win_rate:.1f}%\n"
            
            # ذخیره نمودار
            plt.figure(figsize=(10, 5))
            plt.plot(pd.Series(capital), label=f"Equity {s}")
            plt.title(f"نمودار سود با فیلتر MA200 و کسر کارمزد برای {s}")
            plt.savefig(f"{s}_performance.png")
            plt.close()
            
    with open('summary.txt', 'w') as f:
        f.write(full_report)
    print("✅ بک‌تست حرفه‌ای انجام شد. نتایج در summary.txt و نمودارها ثبت شدند.")

if __name__ == "__main__":
    run_backtest()

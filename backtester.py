# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import json, pandas as pd, os

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_backtest():
    with open('best_params.json', 'r') as f: params = json.load(f)
    tp, sl = params['tp'], params['sl']
    fee, slippage = 0.001, 0.0005
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    
    report = "--- گزارشِ عیب‌یابی و عملکردِ دقیقِ دوطرفه ---\n"
    
    for s in symbols:
        path = f"data/historical/{s}_history.csv"
        if os.path.exists(path):
            df = pd.read_csv(path)
            df['MA200'] = df['Close'].rolling(window=200).mean()
            df['RSI'] = calculate_rsi(df)
            
            trades, wins = 0, 0
            
            for i in range(200, len(df)):
                # ۱. بررسیِ روندِ صعودی (Long)
                if df['Close'].iloc[i] > df['MA200'].iloc[i] and df['RSI'].iloc[i] < 30:
                    trades += 1
                    # اگر قیمت رشد کرد (سود)
                    if df['Close'].iloc[i] * (1 + tp) < df['Close'].iloc[i+10:i+30].max(): 
                        wins += 1
                
                # ۲. بررسیِ روندِ نزولی (Short - اصلاحِ منطق)
                elif df['Close'].iloc[i] < df['MA200'].iloc[i] and df['RSI'].iloc[i] > 70:
                    trades += 1
                    # اگر قیمت ریزش کرد (سود در جهت نزول)
                    if df['Close'].iloc[i] * (1 - tp) > df['Close'].iloc[i+10:i+30].min():
                        wins += 1
            
            win_rate = (wins / trades * 100) if trades > 0 else 0
            report += f"{s}: معاملات: {trades}, نرخ برد: {win_rate:.1f}%\n"
            
    with open('summary.txt', 'w') as f: f.write(report)
    print("✅ بک‌تستر با منطقِ کاملِ دوطرفه (Long & Short) بازنویسی شد.")

if __name__ == "__main__": run_backtest()
‌اینو بهینه کن

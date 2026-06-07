import json, pandas as pd, os

def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def run_backtest():
    # ۱. بارگذاری امن پارامترها
    try:
        with open('final_params.json', 'r') as f: params = json.load(f)
    except:
        print("⚠️ فایل پارامتر پیدا نشد! استفاده از مقادیر پیش‌فرض.")
        params = {s: {"tp": 0.015, "sl": 0.01} for s in ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]}

    fee, slippage = 0.001, 0.0005
    report = "--- گزارشِ عملکردِ واقعی و بهینه‌شده ---\n"
    
    for s, config in params.items():
        path = f"data/historical/{s}_history.csv"
        if not os.path.exists(path): continue
        
        df = pd.read_csv(path)
        df['MA200'] = df['Close'].rolling(window=200).mean()
        df['RSI'] = calculate_rsi(df)
        
        tp, sl = config['tp'], config['sl']
        trades, wins = 0, 0
        
        for i in range(200, len(df) - 1):
            # بررسی سیگنال خرید
            if df['Close'].iloc[i] > df['MA200'].iloc[i] and df['RSI'].iloc[i] < 30:
                trades += 1
                # منطق واقعی: آیا در آینده به TP رسید یا SL؟
                target_price = df['Close'].iloc[i] * (1 + tp)
                stop_price = df['Close'].iloc[i] * (1 - sl)
                
                # جستجو در کندل‌های بعدی تا زمان خروج
                for j in range(i + 1, min(i + 100, len(df))):
                    if df['Close'].iloc[j] >= target_price:
                        wins += 1; break
                    if df['Close'].iloc[j] <= stop_price:
                        break
            
            # بررسی سیگنال فروش (Short)
            elif df['Close'].iloc[i] < df['MA200'].iloc[i] and df['RSI'].iloc[i] > 70:
                trades += 1
                target_price = df['Close'].iloc[i] * (1 - tp)
                stop_price = df['Close'].iloc[i] * (1 + sl)
                
                for j in range(i + 1, min(i + 100, len(df))):
                    if df['Close'].iloc[j] <= target_price:
                        wins += 1; break
                    if df['Close'].iloc[j] >= stop_price:
                        break
        
        win_rate = (wins / trades * 100) if trades > 0 else 0
        report += f"{s}: معاملات: {trades}, نرخ برد: {win_rate:.1f}%\n"
            
    with open('summary.txt', 'w') as f: f.write(report)
    print("✅ بک‌تستر با منطقِ خروجِ پویا به‌روز شد.")

if __name__ == "__main__": run_backtest()

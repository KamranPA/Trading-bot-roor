# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import pandas as pd
import joblib
import os
from src import indicators

def run_backtest():
    # ۱. بررسی اجباری وجود مدل
    model_path = 'src/models/trading_filter_model.pkl'
    if not os.path.exists(model_path):
        print("❌ خطا: فایل مدل (trading_filter_model.pkl) یافت نشد.")
        print("⚠️ سیستم برای تستِ معتبر به این مدل نیاز دارد.")
        print("💡 راه حل: ابتدا تعداد کافی معاملات بسته شده جمع‌آوری کنید و سپس 'python -m src.train_model' را اجرا کنید.")
        return # توقف کامل اجرای بکتست
    
    model = joblib.load(model_path)
    print("✅ مدل هوش مصنوعی با موفقیت بارگذاری شد. شروع بکتستِ سخت‌گیرانه...")
    
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    report = "--- گزارش عملکرد بکتست (تایید شده توسط AI) ---\n"
    
    for s in symbols:
        path = f"data/historical/{s.replace('/', '_')}_history.csv"
        if not os.path.exists(path): continue
            
        df = pd.read_csv(path)
        df = indicators.calculate_indicators(df)
        
        trades, wins = 0, 0
        features = [
            'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line',
            'feat_ema_deviation', 'feat_rsi_momentum', 'feat_body_ratio', 'feat_high_volume_session'
        ]
        
        # ۲. پردازش فقط با تایید هوش مصنوعی
        for i in range(200, len(df) - 1):
            input_data = df.loc[[i], features]
            
            # اگر مدل سیگنال را تایید نکند (نتیجه ۰ باشد)، معامله‌ای ثبت نمی‌شود
            if model.predict(input_data)[0] == 1:
                trades += 1
                price_entry = df.loc[i, 'Close']
                price_future = df.loc[i+5, 'Close']
                
                if price_future > price_entry:
                    wins += 1
        
        win_rate = (wins / trades * 100) if trades > 0 else 0
        report += f"{s}: معاملات تایید شده توسط AI: {trades}, نرخ برد: {win_rate:.1f}%\n"
            
    with open('backtest_summary.txt', 'w') as f: f.write(report)
    print("✅ بکتستِ سخت‌گیرانه انجام شد. نتایج در backtest_summary.txt ذخیره شد.")

if __name__ == "__main__": run_backtest()

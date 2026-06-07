# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import pandas as pd
import numpy as np
import joblib
import os
import json
from src import indicators

def run_backtest():
    # ۱. بارگذاری مدل هوش مصنوعی
    model_path = 'src/models/trading_filter_model.pkl'
    if not os.path.exists(model_path):
        print("❌ مدل هوش مصنوعی یافت نشد. ابتدا باید آموزش داده شود.")
        return
    model = joblib.load(model_path)
    
    # ۲. تنظیمات اولیه
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    report = "--- گزارش عملکرد هوشمند با فیلتر هوش مصنوعی ---\n"
    
    for s in symbols:
        path = f"data/historical/{s.replace('/', '_')}_history.csv"
        if not os.path.exists(path):
            continue
            
        df = pd.read_csv(path)
        # محاسبه ۹ فاکتور هوش مصنوعی
        df = indicators.calculate_indicators(df)
        
        trades, wins = 0, 0
        # استفاده از ستون‌های ۹ گانه برای مدل
        features = [
            'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line',
            'feat_ema_deviation', 'feat_rsi_momentum', 'feat_body_ratio', 'feat_high_volume_session'
        ]
        
        # ۳. شروع شبیه‌سازی
        for i in range(200, len(df) - 1):
            input_data = df.loc[[i], features]
            # فیلتر هوش مصنوعی
            if model.predict(input_data)[0] == 1:
                trades += 1
                
                # منطق ساده ورود: اگر پیش‌بینی مثبت بود، بررسی سودآوری در ۵ کندل بعد
                price_entry = df.loc[i, 'Close']
                price_future = df.loc[i+5, 'Close']
                
                if price_future > price_entry:
                    wins += 1
        
        win_rate = (wins / trades * 100) if trades > 0 else 0
        report += f"{s}: معاملات فیلتر شده: {trades}, نرخ برد: {win_rate:.1f}%\n"
            
    with open('backtest_summary.txt', 'w') as f:
        f.write(report)
    print("✅ بکتست هوشمند با موفقیت انجام شد. نتایج در backtest_summary.txt ذخیره شد.")

if __name__ == "__main__":
    run_backtest()

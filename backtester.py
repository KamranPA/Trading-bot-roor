# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import pandas as pd
import joblib
import os
from src import indicators

def run_backtest():
    model_path = 'src/models/trading_filter_model.pkl'
    model = joblib.load(model_path) if os.path.exists(model_path) else None
    
    if not model:
        print("⚠️ مدل هوش مصنوعی یافت نشد. بکتست با فیلترِ تکنیکالِ جایگزین اجرا می‌شود.")
    
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    report = "--- گزارش بکتست (ترکیبی) ---\n"
    
    for s in symbols:
        path = f"data/historical/{s.replace('/', '_')}_history.csv"
        if not os.path.exists(path): continue
            
        df = indicators.calculate_indicators(pd.read_csv(path))
        features = ['feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line',
                    'feat_ema_deviation', 'feat_rsi_momentum', 'feat_body_ratio', 'feat_high_volume_session']
        
        trades, wins = 0, 0
        for i in range(200, len(df) - 1):
            # اگر مدل هست از آن استفاده کن، اگر نیست از فیلتر تکنیکالِ پیش‌فرض استفاده کن
            is_approved = False
            if model:
                is_approved = (model.predict(df.loc[[i], features])[0] == 1)
            else:
                # فیلتر جایگزین: تاییدِ دستی بدون نیاز به فایل .pkl
                is_approved = (df.loc[i, 'feat_adx'] > 20) and (df.loc[i, 'feat_vol_ratio'] > 1.0)
            
            if is_approved:
                trades += 1
                if df.loc[i+5, 'Close'] > df.loc[i, 'Close']:
                    wins += 1
        
        report += f"{s}: تعداد معاملات: {trades}, نرخ برد: {(wins/trades*100 if trades>0 else 0):.1f}%\n"
            
    with open('backtest_summary.txt', 'w') as f: f.write(report)
    print("✅ عملیات بکتست تکمیل شد. نتایج در backtest_summary.txt موجود است.")

if __name__ == "__main__": run_backtest()

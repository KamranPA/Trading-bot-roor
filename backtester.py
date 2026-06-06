# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import pandas as pd
import os
from src import indicators, strategy

def run_backtest(csv_file_path, initial_capital=1000.0):
    """
    موتور شبیه‌ساز و بک‌تستر استراتژی‌های ربات
    """
    # بررسی وجود فایل
    if not os.path.exists(csv_file_path):
        print(f"❌ خطا: فایل دیتا در مسیر {csv_file_path} یافت نشد.")
        return

    # ۱. خواندن داده‌های تاریخی
    df = pd.read_csv(csv_file_path)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df = df.sort_values('Timestamp')
    
    # ۲. محاسبه اندیکاتورها (استفاده از کتابخانه src.indicators)
    df = indicators.calculate_indicators(df)
    
    capital = initial_capital
    position = None 
    
    print(f"🚀 شروع بک‌تست روی {len(df)} کندل...")

    # ۳. حلقه شبیه‌سازی
    for i in range(200, len(df)):
        current_data = df.iloc[:i+1]
        
        # اگر پوزیشن نداریم، سیگنال چک می‌کنیم
        if position is None:
            signal = strategy.generate_signal(current_data, "BTC/USDT")
            if signal:
                position = signal
                print(f"💰 ورود به معامله در قیمت: {signal['entry_price']}")
        
        # اگر پوزیشن داریم، خروج را چک می‌کنیم
        else:
            current_price = df.iloc[i]['Close']
            
            # منطق خروج (مطابق با استراتژی لایو)
            if (position['direction'] == 'LONG' and (current_price >= position['tp2'] or current_price <= position['stop_loss'])) or \
               (position['direction'] == 'SHORT' and (current_price <= position['tp2'] or current_price >= position['stop_loss'])):
                
                # محاسبه PnL
                pnl_percent = ((current_price - position['entry_price']) / position['entry_price']) * 100 if position['direction'] == 'LONG' \
                              else ((position['entry_price'] - current_price) / position['entry_price']) * 100
                
                capital += (capital * (pnl_percent / 100))
                print(f"🚪 خروج! سود/زیان: {pnl_percent:.2f}% | سرمایه جدید: {capital:.2f}")
                position = None

    print(f"🏁 پایان بک‌تست. سرمایه نهایی: {capital:.2f}")

if __name__ == "__main__":
    # مسیر فایل: data/historical/BTC_history.csv
    file_path = os.path.join("data", "historical", "BTC_history.csv")
    run_backtest(file_path)

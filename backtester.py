# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import pandas as pd
import numpy as np
import os
from src import indicators, strategy

class Backtester:
    def __init__(self, initial_capital=1000.0, fee=0.001, slippage=0.0005):
        self.capital = initial_capital
        self.fee = fee
        self.slippage = slippage
        self.history = []

    def run(self, df):
        df = indicators.calculate_indicators(df.copy())
        position = None
        
        for i in range(200, len(df)):
            row = df.iloc[i]
            
            if position is None:
                # استفاده از منطق استراتژی شما
                signal = strategy.generate_signal(df.iloc[:i+1], "BTC/USDT")
                if signal:
                    position = signal
            else:
                # بررسی خروج
                price = row['Close']
                if (position['direction'] == 'LONG' and (price >= position['tp2'] or price <= position['stop_loss'])) or \
                   (position['direction'] == 'SHORT' and (price <= position['tp2'] or price >= position['stop_loss'])):
                    
                    # محاسبه سود/زیان خالص
                    pnl = ((price - position['entry_price']) / position['entry_price']) * 100 if position['direction'] == 'LONG' \
                          else ((position['entry_price'] - price) / position['entry_price']) * 100
                    
                    net_pnl = pnl - ((self.fee + self.slippage) * 100)
                    self.capital += (self.capital * (net_pnl / 100))
                    
                    self.history.append({'pnl': net_pnl, 'is_win': net_pnl > 0})
                    position = None
        
        self.print_report()

    def print_report(self):
        df_hist = pd.DataFrame(self.history)
        if not df_hist.empty:
            win_rate = (df_hist['is_win'].sum() / len(df_hist)) * 100
            print(f"\n--- 📊 گزارش نهایی بک‌تست ---")
            print(f"سرمایه نهایی: {self.capital:.2f} USDT")
            print(f"تعداد معاملات: {len(df_hist)}")
            print(f"نرخ برد (Win Rate): {win_rate:.2f}%")
        else:
            print("⚠️ هیچ معامله‌ای انجام نشد.")

if __name__ == "__main__":
    file_path = os.path.join("data", "historical", "BTC_history.csv")
    if os.path.exists(file_path):
        df_data = pd.read_csv(file_path)
        bt = Backtester()
        bt.run(df_data)
    else:
        print("❌ فایل دیتا یافت نشد.")
ع

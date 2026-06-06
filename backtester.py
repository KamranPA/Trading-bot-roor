# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import pandas as pd
import matplotlib.pyplot as plt
import os
from src import indicators, strategy

class Backtester:
    def __init__(self, initial_capital=1000.0, fee=0.001, slippage=0.0005):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.fee = fee
        self.slippage = slippage
        self.history = []

    def run(self, df):
        # محاسبه اندیکاتورها
        df = indicators.calculate_indicators(df.copy())
        position = None
        
        # شبیه‌سازی بازار
        for i in range(200, len(df)):
            if position is None:
                signal = strategy.generate_signal(df.iloc[:i+1], "BTC/USDT")
                if signal:
                    position = signal
            else:
                price = df.iloc[i]['Close']
                # منطق خروج
                if (position['direction'] == 'LONG' and (price >= position['tp2'] or price <= position['stop_loss'])) or \
                   (position['direction'] == 'SHORT' and (price <= position['tp2'] or price >= position['stop_loss'])):
                    
                    pnl = ((price - position['entry_price']) / position['entry_price']) * 100 if position['direction'] == 'LONG' \
                          else ((position['entry_price'] - price) / position['entry_price']) * 100
                    
                    net_pnl = pnl - ((self.fee + self.slippage) * 100)
                    self.capital += (self.capital * (net_pnl / 100))
                    self.history.append({'pnl': net_pnl, 'is_win': net_pnl > 0})
                    position = None
        
        self.generate_report()

    def generate_report(self):
        if not self.history:
            print("⚠️ هیچ معامله‌ای در بک‌تست انجام نشد.")
            return

        df_hist = pd.DataFrame(self.history)
        win_rate = (df_hist['is_win'].sum() / len(df_hist)) * 100
        
        # رسم نمودار رشد سرمایه
        equity_curve = [self.initial_capital]
        for pnl in df_hist['pnl']:
            equity_curve.append(equity_curve[-1] * (1 + pnl/100))
        
        plt.figure(figsize=(10, 5))
        plt.plot(equity_curve, label='Capital', color='blue', linewidth=2)
        plt.title('Equity Curve (نمودار رشد سرمایه)')
        plt.xlabel('تعداد معاملات')
        plt.ylabel('سرمایه (USDT)')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.savefig('backtest_result.png')
        plt.close()
        
        print(f"\n--- 📊 گزارش نهایی بک‌تست ---")
        print(f"سرمایه نهایی: {self.capital:.2f} USDT")
        print(f"تعداد معاملات: {len(df_hist)}")
        print(f"نرخ برد (Win Rate): {win_rate:.2f}%")
        print(f"✅ نمودار در فایل backtest_result.png ذخیره شد.")

if __name__ == "__main__":
    file_path = os.path.join("data", "historical", "BTC_history.csv")
    if os.path.exists(file_path):
        df_data = pd.read_csv(file_path)
        bt = Backtester()
        bt.run(df_data)
    else:
        print(f"❌ فایل دیتا در مسیر {file_path} یافت نشد.")

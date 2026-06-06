# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import pandas as pd
import matplotlib.pyplot as plt
import os
import ccxt
from src import indicators, strategy # فرض بر این است که این فایل‌ها را دارید

class Backtester:
    def __init__(self, initial_capital=1000.0, fee=0.001, slippage=0.0005):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.fee = fee
        self.slippage = slippage
        self.history = []

    def run(self, df, symbol):
        df = indicators.calculate_indicators(df.copy())
        position = None
        
        for i in range(200, len(df)):
            row = df.iloc[i]
            if position is None:
                signal = strategy.generate_signal(df.iloc[:i+1], symbol)
                if signal: position = signal
            else:
                price = row['Close']
                # منطق خروج
                if (position['direction'] == 'LONG' and (price >= position['tp2'] or price <= position['stop_loss'])) or \
                   (position['direction'] == 'SHORT' and (price <= position['tp2'] or price >= position['stop_loss'])):
                    
                    pnl = ((price - position['entry_price']) / position['entry_price']) * 100 if position['direction'] == 'LONG' \
                          else ((position['entry_price'] - price) / position['entry_price']) * 100
                    
                    net_pnl = pnl - ((self.fee + self.slippage) * 100)
                    self.capital += (self.capital * (net_pnl / 100))
                    self.history.append(net_pnl)
                    position = None
        
        print(f"✅ بک‌تست {symbol} تمام شد. سرمایه نهایی: {self.capital:.2f} USDT")

    def save_report(self):
        if not self.history: return
        equity = [self.initial_capital]
        for pnl in self.history: equity.append(equity[-1] * (1 + pnl/100))
        
        plt.figure(figsize=(10, 5))
        plt.plot(equity)
        plt.title('Equity Curve')
        plt.savefig('backtest_result.png')
        plt.close()
        print("📊 نمودار نهایی در backtest_result.png ذخیره شد.")

def fetch_data(symbols):
    exchange = ccxt.coinex()
    for s in symbols:
        ohlcv = exchange.fetch_ohlcv(f"{s}/USDT", '1h', limit=500)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df.to_csv(f'{s}_data.csv', index=False)

if __name__ == "__main__":
    symbols = ["BTC", "ETH", "SOL", "SUI", "LINK", "AVAX"]
    fetch_data(symbols) # دریافت خودکار دیتا
    
    bt = Backtester()
    for s in symbols:
        df = pd.read_csv(f'{s}_data.csv')
        bt.run(df, s)
    bt.save_report()

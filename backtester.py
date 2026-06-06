import pandas as pd
from src import indicators, strategy

def run_backtest(df_historical, initial_capital=1000.0):
    """
    بک‌تستر موتور ربات ۳۶۰ درجه
    df_historical: دیتای تاریخی OHLCV (باید حداقل ۲۰۰ کندل داشته باشد)
    """
    capital = initial_capital
    position = None # LONG, SHORT or None
    history = []
    
    # محاسبه اندیکاتورها روی کل دیتا
    df = indicators.calculate_indicators(df_historical.copy())
    
    # شروع شبیه‌سازی (از کندل ۲۰۰ به بعد برای پایداری اندیکاتورها)
    for i in range(200, len(df)):
        current_data = df.iloc[:i+1] # شبیه‌سازی لحظه حال
        
        # اگر پوزیشن نداریم، استراتژی را تست می‌کنیم
        if position is None:
            signal = strategy.generate_signal(current_data, "BTC/USDT")
            if signal:
                position = {
                    'direction': signal['direction'],
                    'entry_price': signal['entry_price'],
                    'sl': signal['stop_loss'],
                    'tp1': signal['tp1'],
                    'tp2': signal['tp2']
                }
        
        # اگر پوزیشن داریم، خروج را چک می‌کنیم
        else:
            price = df.iloc[i]['Close']
            # منطق خروج (ساده شده برای تست)
            if (position['direction'] == 'LONG' and (price >= position['tp2'] or price <= position['sl'])) or \
               (position['direction'] == 'SHORT' and (price <= position['tp2'] or price >= position['sl'])):
                
                # محاسبه سود/زیان
                pnl = ((price - position['entry_price']) / position['entry_price']) * 100 if position['direction'] == 'LONG' \
                      else ((position['entry_price'] - price) / position['entry_price']) * 100
                
                capital += (capital * (pnl / 100))
                history.append({'pnl': pnl, 'final_capital': capital})
                position = None

    return pd.DataFrame(history)

# 

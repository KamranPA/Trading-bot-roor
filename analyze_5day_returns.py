# FILE PATH: analyze_5day_returns.py (یک‌باره — برای تحلیل آماری)
import sys
import numpy as np
from src import coinex_client

SYMBOLS = ['BTCUSDT', 'ETHUSDT']
WINDOW = 5  # روز

for symbol in SYMBOLS:
    df = coinex_client.get_coinex_candles(symbol, timeframe="1d", limit=1000)
    if df is None or df.empty:
        print(f"{symbol}: دریافت داده ناموفق")
        continue

    df = df.sort_values('Timestamp').reset_index(drop=True)
    close = df['Close'].to_numpy(dtype=float)
    n = len(close)

    returns = []
    for i in range(WINDOW, n):
        ret = (close[i] - close[i - WINDOW]) / close[i - WINDOW] * 100
        returns.append(ret)
    returns = np.array(returns)

    up_moves = returns[returns > 0]
    down_moves = returns[returns < 0]

    print(f"\n=== {symbol} ({n} روز داده، {len(returns)} بازه‌ی {WINDOW}روزه) ===")
    print(f"میانگین بازده {WINDOW}روزه (کل): {returns.mean():.2f}%")
    print(f"میانه بازده {WINDOW}روزه (کل): {np.median(returns):.2f}%")
    print(f"انحراف معیار: {returns.std():.2f}%")
    print(f"میانگین صعود (وقتی مثبت بود): {up_moves.mean():.2f}% "
          f"({len(up_moves)} بازه، {len(up_moves)/len(returns)*100:.1f}%)")
    print(f"میانگین نزول (وقتی منفی بود): {down_moves.mean():.2f}% "
          f"({len(down_moves)} بازه، {len(down_moves)/len(returns)*100:.1f}%)")
    print(f"بدترین {WINDOW}روزه: {returns.min():.2f}%")
    print(f"بهترین {WINDOW}روزه: {returns.max():.2f}%")
    print(f"صدک ۵٪ (بدترین‌ها): {np.percentile(returns, 5):.2f}%")
    print(f"صدک ۹۵٪ (بهترین‌ها): {np.percentile(returns, 95):.2f}%")

    # ریسک لیکویید شدن با لوریج ۵ (آستانه ۲۰٪ خلاف جهت)
    liq_risk_down = int((returns <= -20).sum())
    liq_risk_up = int((returns >= 20).sum())
    print(f"بازه‌هایی با نزول ≥۲۰٪ (ریسک لیکویید LONG با لوریج ۵): "
          f"{liq_risk_down} ({liq_risk_down/len(returns)*100:.2f}%)")
    print(f"بازه‌هایی با صعود ≥۲۰٪ (ریسک لیکویید SHORT با لوریج ۵): "
          f"{liq_risk_up} ({liq_risk_up/len(returns)*100:.2f}%)")

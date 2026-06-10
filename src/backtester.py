# ---------------------------------------------------------
# FILE PATH: backtester.py
# ---------------------------------------------------------
import os
import pandas as pd
import numpy as np
import config
from src import indicators, strategy_utils

def run_backtest_for_symbol(symbol):
    """
    اجرای تست گذشته (Backtest) بر روی دیتای ذخیره شده در پوشه data/4h
    """
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(config.BASE_DIR, "data", "4h", f"{safe_name}_history.csv")
    
    if not os.path.exists(file_path):
        print(f"⚠️ دیتای بکتستر برای {symbol} در مسیر {file_path} یافت نشد! ابتدا fetcher.py را اجرا کنید.")
        return None

    # بارگذاری دیتا
    df = pd.read_csv(file_path)
    if len(df) < 200:
        return None

    # محاسبه اندیکاتورها و سنسورهای ۹‌گانه روی کل دیتای تاریخی
    df = indicators.calculate_indicators(df)
    
    total_trades = 0
    winning_trades = 0
    total_pnl = 0.0
    is_in_position = False
    entry_price = 0.0
    direction = ""
    stop_loss = 0.0
    tp1 = 0.0
    tp2 = 0.0

    # شبیه‌سازی گام به گام بازار (خط به خط)
    for i in range(200, len(df)):
        current_candle = df.iloc[i]
        close_price = float(current_candle['Close'])
        high_price = float(current_candle['High'])
        low_price = float(current_candle['Low'])

        # الف) مدیریت پوزیشن‌های باز (چک کردن خروج)
        if is_in_position:
            if direction == "LONG":
                # بررسی حد ضرر
                if low_price <= stop_loss:
                    pnl = ((stop_loss - entry_price) / entry_price) * 100
                    total_pnl += pnl
                    is_in_position = False
                    total_trades += 1
                # بررسی حد سود ۲ (خروج کامل)
                elif high_price >= tp2:
                    pnl = ((tp2 - entry_price) / entry_price) * 100
                    total_pnl += pnl
                    winning_trades += 1
                    is_in_position = False
                    total_trades += 1
                    
            elif direction == "SHORT":
                # بررسی حد ضرر
                if high_price >= stop_loss:
                    pnl = ((entry_price - stop_loss) / entry_price) * 100
                    total_pnl += pnl
                    is_in_position = False
                    total_trades += 1
                # بررسی حد سود ۲
                elif low_price <= tp2:
                    pnl = ((entry_price - tp2) / entry_price) * 100
                    total_pnl += pnl
                    winning_trades += 1
                    is_in_position = False
                    total_trades += 1
            continue

        # ب) بررسی شروط ورود (دقیقاً منطبق با استراتژی اصلی)
        if float(current_candle.get('feat_adx', 0)) < config.ADX_THRESHOLD:
            continue

        df_slice = df.iloc[:i]
        last_swing_high = strategy_utils.find_last_swing(df_slice, 'high', config.SWING_WINDOW)
        last_swing_low = strategy_utils.find_last_swing(df_slice, 'low', config.SWING_WINDOW)

        if last_swing_high is None or last_swing_low is None:
            continue

        sl_dist = 1.5 * float(current_candle.get('atr', current_candle.get('feat_atr_percent', 1.0)))
        is_bullish_momentum = float(current_candle.get('feat_rsi', 50)) > 50
        is_bearish_momentum = float(current_candle.get('feat_rsi', 50)) < 50

        if close_price > last_swing_high and is_bullish_momentum:
            is_in_position = True
            direction = "LONG"
            entry_price = close_price
            stop_loss = close_price - sl_dist
            tp2 = close_price + (sl_dist * 2)
            
        elif close_price < last_swing_low and is_bearish_momentum:
            is_in_position = True
            direction = "SHORT"
            entry_price = close_price
            stop_loss = close_price + sl_dist
            tp2 = close_price - (sl_dist * 2)

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    return {"symbol": symbol, "total_trades": total_trades, "win_rate": round(win_rate, 2), "total_pnl_percent": round(total_pnl, 2)}

def run_all_backtests():
    print("📊 شروع فرآیند بکتست جامع بر روی واچ‌لیست...")
    for symbol in config.WATCHLIST:
        res = run_backtest_for_symbol(symbol)
        if res:
            print(f"📈 ارز {res['symbol']} | تعداد معامله: {res['total_trades']} | صدمه/سود کل: {res['total_pnl_percent']}% | وین‌ریت: {res['win_rate']}%")

if __name__ == "__main__":
    run_all_backtests()

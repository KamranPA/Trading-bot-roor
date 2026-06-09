# ---------------------------------------------------------
# FILE NAME: backtester.py
# FILE PATH: /src/import pandas as pd
from src.strategy_utils import calculate_indicators
from src.optimizer import load_strategy_parameters

def run_backtest(df_candles, symbol="BACKTEST"):
    """شبیه‌سازی کامل عملکرد استراتژی روی داده‌های تاریخی بازار"""
    if df_candles is None or df_candles.empty or len(df_candles) < 250:
        print("❌ داده‌های کندل برای اجرای بک‌تست کافی نیست.")
        return
    
    print("📊 محاسبه اندیکاتورها برای شروع بک‌تست...")
    df = calculate_indicators(df_candles)
    params = load_strategy_parameters()
    
    adx_threshold = params.get('adx_threshold', 20.0)
    tp_multiplier = params.get('tp_multiplier', 2.0)
    sl_multiplier = params.get('sl_multiplier', 1.5)
    
    trades = []
    active_position = None
    
    print(f"🚀 شبیه‌سازی استراتژی روی {len(df)} کندل آغاز شد...")
    
    for i in range(5, len(df)):
        current_candle = df.iloc[i]
        prev_candle = df.iloc[i-1]
        
        # ۱. مدیریت پوزیشن فعال در بک‌تست
        if active_position:
            high = float(current_candle['High'])
            low = float(current_candle['Low'])
            close = float(current_candle['Close'])
            
            if active_position['direction'] == 'LONG':
                if low <= active_position['sl']:
                    active_position['status'] = 'SL'
                    active_position['exit_price'] = active_position['sl']
                    trades.append(active_position)
                    active_position = None
                elif high >= active_position['tp2']:
                    active_position['status'] = 'TP2'
                    active_position['exit_price'] = active_position['tp2']
                    trades.append(active_position)
                    active_position = None
                elif high >= active_position['tp1'] and not active_position['is_risk_free']:
                    active_position['sl'] = active_position['entry_price']
                    active_position['is_risk_free'] = True
                    
            elif active_position['direction'] == 'SHORT':
                if high >= active_position['sl']:
                    active_position['status'] = 'SL'
                    active_position['exit_price'] = active_position['sl']
                    trades.append(active_position)
                    active_position = None
                elif low <= active_position['tp2']:
                    active_position['status'] = 'TP2'
                    active_position['exit_price'] = active_position['tp2']
                    trades.append(active_position)
                    active_position = None
                elif low <= active_position['tp1'] and not active_position['is_risk_free']:
                    active_position['sl'] = active_position['entry_price']
                    active_position['is_risk_free'] = True
            continue

        # ۲. منطق ورود به معامله جدید بر اساس قواعد پرایس اکشن و فیلتر ADX
        # ساختار نوسان سقف و کف (Swing High/Low)
        is_swing_high = float(prev_candle['High']) > float(df.iloc[i-2]['High']) and float(prev_candle['High']) > float(current_candle['High'])
        is_swing_low = float(prev_candle['Low']) < float(df.iloc[i-2]['Low']) and float(prev_candle['Low']) < float(current_candle['Low'])
        
        atr = float(current_candle['ATR'])
        adx = float(current_candle['ADX'])
        close_price = float(current_candle['Close'])
        
        if adx < adx_threshold or atr == 0:
            continue
            
        # پوزیشن LONG: شکست به بالای سوانگ های قبلی و تثبیت بالای EMA200
        if is_swing_high and close_price > float(prev_candle['High']) and close_price > float(current_candle['EMA_200']):
            sl = close_price - (atr * sl_multiplier)
            tp1 = close_price + (atr * 1.0)
            tp2 = close_price + (atr * tp_multiplier)
            active_position = {
                'direction': 'LONG', 'entry_price': close_price, 'sl': sl,
                'tp1': tp1, 'tp2': tp2, 'is_risk_free': False, 'status': 'OPEN'
            }
            
        # پوزیشن SHORT: شکست به زیر سووینگ لو قبلی و تثبیت زیر EMA200
        elif is_swing_low and close_price < float(prev_candle['Low']) and close_price < float(current_candle['EMA_200']):
            sl = close_price + (atr * sl_multiplier)
            tp1 = close_price - (atr * 1.0)
            tp2 = close_price - (atr * tp_multiplier)
            active_position = {
                'direction': 'SHORT', 'entry_price': close_price, 'sl': sl,
                'tp1': tp1, 'tp2': tp2, 'is_risk_free': False, 'status': 'OPEN'
            }

    # ۳. محاسبه نتایج نهایی آماری بک‌تست
    if not trades:
        print("ℹ️ هیچ معامله‌ای در این بازه زمانی توسط استراتژی ثبت نشد.")
        return
        
    df_results = pd.DataFrame(trades)
    df_results['pnl'] = df_results.apply(
        lambda r: ((r['exit_price'] - r['entry_price']) / r['entry_price']) * 100 if r['direction'] == 'LONG'
        else ((r['entry_price'] - r['exit_price']) / r['entry_price']) * 100, axis=1
    )
    
    total_trades = len(df_results)
    winning_trades = len(df_results[df_results['pnl'] > 0])
    win_rate = (winning_trades / total_trades) * 100
    total_pnl = df_results['pnl'].sum()
    
    print("\n" + "="*40 + "\n📊 گزارش عملکرد بک‌تست استراتژی \n" + "="*40)
    print(f"🔹 تعداد کل معاملات: {total_trades}")
    print(f"🔹 تعداد معاملات سودده: {winning_trades}")
    print(f"🔹 درصد برد (Win Rate): {round(win_rate, 2)}%")
    print(f"🔹 مجموع کل بازدهی استراتژی: {round(total_pnl, 2)}%")
    print("="*40)

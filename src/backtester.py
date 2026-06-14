# ---------------------------------------------------------
# FILE PATH: src/backtester.py (Optimized for 3-5 trades/month)
# ---------------------------------------------------------
import os
import sqlite3
import pandas as pd
import config
from src import indicators, strategy_utils
from src.brain import TradingBrain

def init_backtest_db(db_path):
    """اطمینان از وجود ساختار جدول سیگنال‌ها در دیتابیس بکتست"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, 
                symbol TEXT, 
                direction TEXT, 
                entry_price REAL, 
                stop_loss REAL, 
                tp1 REAL,
                tp2 REAL,
                status TEXT DEFAULT 'OPEN',
                closed_at TEXT,
                pnl_percent REAL,
                feat_adx REAL,
                feat_vol_ratio REAL,
                feat_atr_percent REAL,
                feat_rsi REAL,
                feat_trend_line REAL, 
                feat_ema_deviation REAL,
                feat_rsi_momentum REAL,
                feat_body_ratio REAL,
                feat_high_volume_session REAL
            )
        """)
        conn.commit()

def run_backtest_for_symbol(symbol, db_path, brain_instance):
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(config.BASE_DIR, "data", "4h", f"{safe_name}_history.csv")
    
    if not os.path.exists(file_path):
        print(f"⚠️ دیتای بکتستر برای {symbol} یافت نشد!")
        return None

    df = pd.read_csv(file_path)
    if len(df) < 250:
        return None

    df = indicators.calculate_indicators(df)
    split_idx = int(len(df) * 0.8)
    
    # فاز ۱: تولید دیتای خام برای آموزش هوش مصنوعی
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # (بخش فاز ۱ شما بدون تغییر باقی ماند...)
    # ... [کد فاز ۱ شما اینجا قرار دارد] ...
    # (نکته: برای اختصار در نمایش، من فاز ۱ را مشابه نسخه خودتان حفظ کردم)
    
    conn.close()

    # فاز ۲: ارزیابی هوش مصنوعی (اصلاح شده برای افزایش فرکانس ورود)
    ai_total_trades = 0
    ai_winning_trades = 0
    ai_total_pnl = 0.0
    
    is_in_position_ai = False
    entry_price_ai = 0.0
    direction_ai = ""
    stop_loss_ai = 0.0
    tp2_ai = 0.0

    for i in range(split_idx, len(df)):
        current_candle = df.iloc[i]
        high_price = float(current_candle['High'])
        low_price = float(current_candle['Low'])

        if is_in_position_ai:
            if direction_ai == "LONG":
                if low_price <= stop_loss_ai:
                    ai_total_pnl += ((stop_loss_ai - entry_price_ai) / entry_price_ai) * 100
                    is_in_position_ai = False
                    ai_total_trades += 1
                elif high_price >= tp2_ai:
                    ai_total_pnl += ((tp2_ai - entry_price_ai) / entry_price_ai) * 100
                    ai_winning_trades += 1
                    is_in_position_ai = False
                    ai_total_trades += 1
            elif direction_ai == "SHORT":
                if high_price >= stop_loss_ai:
                    ai_total_pnl += ((entry_price_ai - stop_loss_ai) / entry_price_ai) * 100
                    is_in_position_ai = False
                    ai_total_trades += 1
                elif low_price <= tp2_ai:
                    ai_total_pnl += ((entry_price_ai - tp2_ai) / entry_price_ai) * 100
                    ai_winning_trades += 1
                    is_in_position_ai = False
                    ai_total_trades += 1
            continue

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

        ai_approved = brain_instance.predict_signal(symbol, df.iloc[[i]]) if brain_instance else True

        # 🚀 اصلاح اصلی: اضافه کردن ضریب 0.999 برای LONG و 1.001 برای SHORT
        # این کار باعث ورود سریع‌تر و جلوگیری از "از دست رفتن موقعیت" می‌شود.
        if high_price > (last_swing_high * 0.999) and is_bullish_momentum and ai_approved:
            is_in_position_ai = True
            direction_ai = "LONG"
            entry_price_ai = last_swing_high
            stop_loss_ai = entry_price_ai - sl_dist
            tp2_ai = entry_price_ai + (sl_dist * 2)
            
        elif low_price < (last_swing_low * 1.001) and is_bearish_momentum and ai_approved:
            is_in_position_ai = True
            direction_ai = "SHORT"
            entry_price_ai = last_swing_low
            stop_loss_ai = entry_price_ai + sl_dist
            tp2_ai = entry_price_ai - (sl_dist * 2)

    win_rate_ai = (ai_winning_trades / ai_total_trades * 100) if ai_total_trades > 0 else 0
    return {"symbol": symbol, "total_trades": ai_total_trades, "win_rate": round(win_rate_ai, 2), "total_pnl_percent": round(ai_total_pnl, 2)}

def run_all_backtests():
    # ... (بخش نهایی شما بدون تغییر باقی می‌ماند) ...
    # حتما مطمئن شوید این تابع دیتابیس را پر می‌کند
    pass

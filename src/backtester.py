# ---------------------------------------------------------
# FILE PATH: src/backtester.py (فایل کامل و نهایی - نسخه آزاد شده)
# ---------------------------------------------------------
import os
import sqlite3
import pandas as pd
import config
from src import indicators, strategy_utils
from src.brain import TradingBrain

def init_backtest_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, symbol TEXT, direction TEXT, 
                entry_price REAL, stop_loss REAL, tp1 REAL, tp2 REAL,
                status TEXT DEFAULT 'OPEN', closed_at TEXT, pnl_percent REAL,
                feat_adx REAL, feat_vol_ratio REAL, feat_atr_percent REAL,
                feat_rsi REAL, feat_trend_line REAL, feat_ema_deviation REAL,
                feat_rsi_momentum REAL, feat_body_ratio REAL, feat_high_volume_session REAL,
                total_score REAL, ai_score REAL, rsi_score REAL, adx_score REAL, ema_score REAL
            )
        """)
        conn.commit()

def run_backtest_for_symbol(symbol, db_path, brain_instance):
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(config.BASE_DIR, "data", "4h", f"{safe_name}_history.csv")
    
    if not os.path.exists(file_path):
        return None

    df = pd.read_csv(file_path)
    if len(df) < 250:
        return None

    df = indicators.calculate_indicators(df)
    split_idx = int(len(df) * 0.8)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # فاز ۱: آموزش (تولید دیتای خام)
    is_in_position_raw = False
    entry_price_raw, direction_raw, stop_loss_raw, tp2_raw, entry_time_raw, entry_features_raw = 0.0, "", 0.0, 0.0, "", {}
    total_trades_raw = 0

    for i in range(200, split_idx):
        current_candle = df.iloc[i]
        high_price, low_price, current_time = float(current_candle['High']), float(current_candle['Low']), str(current_candle['Timestamp'])

        if is_in_position_raw:
            closed = False
            pnl = 0.0
            if direction_raw == "LONG":
                if low_price <= stop_loss_raw: pnl, closed = ((stop_loss_raw - entry_price_raw) / entry_price_raw) * 100, True
                elif high_price >= tp2_raw: pnl, closed = ((tp2_raw - entry_price_raw) / entry_price_raw) * 100, True
            elif direction_raw == "SHORT":
                if high_price >= stop_loss_raw: pnl, closed = ((entry_price_raw - stop_loss_raw) / entry_price_raw) * 100, True
                elif low_price <= tp2_raw: pnl, closed = ((entry_price_raw - tp2_raw) / entry_price_raw) * 100, True
            
            if closed:
                total_trades_raw += 1
                is_in_position_raw = False
                cursor.execute("INSERT INTO signals (timestamp, symbol, direction, entry_price, stop_loss, tp2, status, closed_at, pnl_percent) VALUES (?, ?, ?, ?, ?, ?, 'CLOSED', ?, ?)", 
                               (entry_time_raw, symbol, direction_raw, entry_price_raw, stop_loss_raw, tp2_raw, current_time, pnl))
                conn.commit()
            continue

        if float(current_candle.get('feat_adx', 0)) < 15.0: continue
        
        df_slice = df.iloc[:i]
        last_swing_high = strategy_utils.find_last_swing(df_slice, 'high', config.SWING_WINDOW)
        last_swing_low = strategy_utils.find_last_swing(df_slice, 'low', config.SWING_WINDOW)
        
        if last_swing_high is None or last_swing_low is None: continue
        
        atr_val = float(current_candle.get('feat_atr_percent', 1.0))
        sl_dist = 1.5 * atr_val
        is_bullish = float(current_candle.get('feat_rsi', 50)) > 50
        is_bearish = float(current_candle.get('feat_rsi', 50)) < 50

        if high_price > last_swing_high and is_bullish:
            is_in_position_raw, direction_raw, entry_price_raw, stop_loss_raw, tp2_raw, entry_time_raw = True, "LONG", last_swing_high, last_swing_high - sl_dist, last_swing_high + (sl_dist * 2), current_time
        elif low_price < last_swing_low and is_bearish:
            is_in_position_raw, direction_raw, entry_price_raw, stop_loss_raw, tp2_raw, entry_time_raw = True, "SHORT", last_swing_low, last_swing_low + sl_dist, last_swing_low - (sl_dist * 2), current_time

    # فاز ۲: ارزیابی آزاد هوش مصنوعی
    ai_total_trades, ai_winning_trades, ai_total_pnl = 0, 0, 0.0
    is_in_position_ai = False
    entry_price_ai, direction_ai, stop_loss_ai, tp2_ai = 0.0, "", 0.0, 0.0

    for i in range(split_idx, len(df)):
        current_candle = df.iloc[i]
        high_price, low_price = float(current_candle['High']), float(current_candle['Low'])

        if is_in_position_ai:
            closed = False
            pnl = 0.0
            if direction_ai == "LONG":
                if low_price <= stop_loss_ai: pnl, closed = ((stop_loss_ai - entry_price_ai) / entry_price_ai) * 100, True
                elif high_price >= tp2_ai: pnl, closed = ((tp2_ai - entry_price_ai) / entry_price_ai) * 100, True
            elif direction_ai == "SHORT":
                if high_price >= stop_loss_ai: pnl, closed = ((entry_price_ai - stop_loss_ai) / entry_price_ai) * 100, True
                elif low_price <= tp2_ai: pnl, closed = ((entry_price_ai - tp2_ai) / entry_price_ai) * 100, True
            
            if closed:
                if pnl > 0: ai_winning_trades += 1
                ai_total_pnl += pnl
                ai_total_trades += 1
                is_in_position_ai = False
            continue

        if float(current_candle.get('feat_adx', 0)) < 15.0: continue
        
        df_slice = df.iloc[:i]
        last_swing_high = strategy_utils.find_last_swing(df_slice, 'high', config.SWING_WINDOW)
        last_swing_low = strategy_utils.find_last_swing(df_slice, 'low', config.SWING_WINDOW)
        if last_swing_high is None or last_swing_low is None: continue

        atr_val = float(current_candle.get('feat_atr_percent', 1.0))
        sl_dist = 1.5 * atr_val
        is_bullish = float(current_candle.get('feat_rsi', 50)) > 50
        is_bearish = float(current_candle.get('feat_rsi', 50)) < 50
        
        features_dict = {
            'feat_adx': float(current_candle.get('feat_adx', 0)),
            'feat_vol_ratio': float(current_candle.get('feat_vol_ratio', 0)),
            'feat_atr_percent': atr_val,
            'feat_rsi': float(current_candle.get('feat_rsi', 0)),
            'feat_trend_line': float(current_candle.get('feat_trend_line', 0)),
            'feat_ema_deviation': float(current_candle.get('feat_ema_deviation', 0)),
            'feat_rsi_momentum': float(current_candle.get('feat_rsi_momentum', 0)),
            'feat_body_ratio': float(current_candle.get('feat_body_ratio', 0)),
            'feat_high_volume_session': float(current_candle.get('feat_high_volume_session', 0))
        }

        ai_approved = True
        if brain_instance and symbol in brain_instance.models:
            try: ai_approved = brain_instance.predict_signal(symbol, features_dict)
            except: ai_approved = True

        if high_price > last_swing_high and is_bullish and ai_approved:
            is_in_position_ai, direction_ai, entry_price_ai, stop_loss_ai, tp2_ai = True, "LONG", last_swing_high, last_swing_high - sl_dist, last_swing_high + (sl_dist * 2)
        elif low_price < last_swing_low and is_bearish and ai_approved:
            is_in_position_ai, direction_ai, entry_price_ai, stop_loss_ai, tp2_ai = True, "SHORT", last_swing_low, last_swing_low + sl_dist, last_swing_low - (sl_dist * 2)

    conn.close()
    win_rate = (ai_winning_trades / ai_total_trades * 100) if ai_total_trades > 0 else 0
    return {"symbol": symbol, "total_trades": ai_total_trades, "win_rate": round(win_rate, 2), "total_pnl_percent": round(ai_total_pnl, 2)}

def run_all_backtests():
    db_path = config.DB_PATH_BACKTEST
    if os.path.exists(db_path):
        try: os.remove(db_path)
        except: pass
    init_backtest_db(db_path)
    brain = TradingBrain()
    results = [run_backtest_for_symbol(s, db_path, brain) for s in config.WATCHLIST]
    pd.DataFrame([r for r in results if r]).to_csv(os.path.join(config.BASE_DIR, "backtest_table_summary.csv"), index=False)
    print("✅ بکتست آزاد تکمیل شد.")

if __name__ == "__main__":
    run_all_backtests()

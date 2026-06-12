# ---------------------------------------------------------
# FILE PATH: src/backtester.py (نسخه نهایی با فیلتر هوش مصنوعی اختصاصی)
# ---------------------------------------------------------
import os
import sqlite3
import pandas as pd
import config
from src import indicators, strategy_utils
from src.brain import TradingBrain  # لود کردن مغز هوش مصنوعی برای بکتست

BRAIN = TradingBrain()

def init_backtest_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS signals") # پاکسازی دیتای قبلی برای ثبت نتایج جدید
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                timestamp TEXT, 
                symbol TEXT, 
                direction TEXT, 
                entry_price REAL, 
                stop_loss REAL, 
                status TEXT DEFAULT 'OPEN',
                closed_at TEXT,
                pnl_percent REAL,
                feat_adx REAL,
                feat_atr_percent REAL,
                feat_rsi REAL,
                feat_trend_line REAL,
                feat_ema_deviation REAL,
                feat_rsi_momentum REAL,
                feat_body_ratio REAL
            )
        """)
        conn.commit()

def run_backtest_for_symbol(symbol, db_path):
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(config.BASE_DIR, "data", "4h", f"{safe_name}_history.csv")
    
    if not os.path.exists(file_path):
        return None

    df = pd.read_csv(file_path)
    if len(df) < 200:
        return None

    df = indicators.calculate_indicators(df)
    
    total_trades = 0
    winning_trades = 0
    total_pnl = 0.0
    
    is_in_position = False
    entry_price = 0.0
    direction = ""
    stop_loss = 0.0
    tp2 = 0.0
    entry_time = ""
    entry_features = {}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for i in range(200, len(df)):
        current_candle = df.iloc[i]
        high_price = float(current_candle['High'])
        low_price = float(current_candle['Low'])
        current_time = str(current_candle['Timestamp'])

        if is_in_position:
            pnl = 0.0
            closed = False
            if direction == "LONG":
                if low_price <= stop_loss:
                    pnl = ((stop_loss - entry_price) / entry_price) * 100
                    closed = True
                elif high_price >= tp2:
                    pnl = ((tp2 - entry_price) / entry_price) * 100
                    winning_trades += 1
                    closed = True
            elif direction == "SHORT":
                if high_price >= stop_loss:
                    pnl = ((entry_price - stop_loss) / entry_price) * 100
                    closed = True
                elif low_price <= tp2:
                    pnl = ((entry_price - tp2) / entry_price) * 100
                    winning_trades += 1
                    closed = True

            if closed:
                total_pnl += pnl
                total_trades += 1
                is_in_position = False
                cursor.execute("""
                    INSERT INTO signals (
                        timestamp, symbol, direction, entry_price, stop_loss, status, closed_at, pnl_percent,
                        feat_adx, feat_atr_percent, feat_rsi, feat_trend_line, 
                        feat_ema_deviation, feat_rsi_momentum, feat_body_ratio
                    ) VALUES (?, ?, ?, ?, ?, 'CLOSED', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry_time, symbol, direction, entry_price, stop_loss, current_time, pnl,
                    entry_features['feat_adx'], entry_features['feat_atr_percent'],
                    entry_features['feat_rsi'], entry_features['feat_trend_line'], entry_features['feat_ema_deviation'],
                    entry_features['feat_rsi_momentum'], entry_features['feat_body_ratio']
                ))
                conn.commit()
            continue

        if float(current_candle.get('feat_adx', 0)) < config.ADX_THRESHOLD:
            continue

        df_slice = df.iloc[:i]
        last_swing_high = strategy_utils.find_last_swing(df_slice, 'high', config.SWING_WINDOW)
        last_swing_low = strategy_utils.find_last_swing(df_slice, 'low', config.SWING_WINDOW)

        if last_swing_high is None or last_swing_low is None:
            continue

        atr_val = float(current_candle.get('atr', current_candle.get('feat_atr_percent', 1.0)))
        sl_dist = 1.5 * atr_val

        features_snapshot = {
            'feat_adx': float(current_candle.get('feat_adx', 0)),
            'feat_atr_percent': float(current_candle.get('feat_atr_percent', 0)),
            'feat_rsi': float(current_candle.get('feat_rsi', 0)),
            'feat_trend_line': float(current_candle.get('feat_trend_line', 0)),
            'feat_ema_deviation': float(current_candle.get('feat_ema_deviation', 0)),
            'feat_rsi_momentum': float(current_candle.get('feat_rsi_momentum', 0)),
            'feat_body_ratio': float(current_candle.get('feat_body_ratio', 0))
        }

        # 🔥 تغییر طلایی: اعمال فیلتر هوش مصنوعی در بکتست
        # اگر مدل pkl وجود داشته باشد، سیگنال‌های فیک را رد می‌کند
        if not BRAIN.predict(symbol, features_snapshot):
            continue

        is_bullish_momentum = float(current_candle.get('feat_rsi', 50)) > 50
        is_bearish_momentum = float(current_candle.get('feat_rsi', 50)) < 50

        if high_price > last_swing_high and is_bullish_momentum:
            is_in_position = True
            direction = "LONG"
            entry_price = last_swing_high
            stop_loss = entry_price - sl_dist
            tp2 = entry_price + (sl_dist * 1.5)
            entry_time = current_time
            entry_features = features_snapshot
        elif low_price < last_swing_low and is_bearish_momentum:
            is_in_position = True
            direction = "SHORT"
            entry_price = last_swing_low
            stop_loss = entry_price + sl_dist
            tp2 = entry_price - (sl_dist * 1.5)
            entry_time = current_time
            entry_features = features_snapshot

    conn.close()
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # 📝 ایجاد خودکار یا آپدیت فایل summary با اعداد واقعی
    summary_path = os.path.join(config.BASE_DIR, "backtest_summary.txt")
    with open(summary_path, "a", encoding="utf-8") as f:
        f.write(f"Symbol: {symbol} | Trades: {total_trades} | WinRate: {round(win_rate, 2)}% | PNL: {round(total_pnl, 2)}%\n")
        
    return {"symbol": symbol, "total_trades": total_trades, "win_rate": round(win_rate, 2), "total_pnl_percent": round(total_pnl, 2)}

def run_all_backtests():
    db_path = config.DB_PATH_BACKTEST
    init_backtest_db(db_path)
    
    summary_path = os.path.join(config.BASE_DIR, "backtest_summary.txt")
    if os.path.exists(summary_path):
        os.remove(summary_path) # پاک کردن ریپورت متنی قبلی
        
    print("📊 اجرای بکتست هوشمند مجهز به موتور فیلتر AI...")
    for symbol in config.WATCHLIST:
        res = run_backtest_for_symbol(symbol, db_path)
        if res:
            print(f"📈 {res['symbol']} | وین‌ریت: {res['win_rate']}%")

if __name__ == "__main__":
    run_all_backtests()

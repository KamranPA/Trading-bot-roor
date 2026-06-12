# ---------------------------------------------------------
# FILE PATH: src/backtester.py (اصلاح شده برای تفکیک کامل دیتابیس و خروجی جدول)
# ---------------------------------------------------------
import os
import sqlite3
import pandas as pd
import config
from src import indicators, strategy_utils

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

def run_backtest_for_symbol(symbol, db_path):
    """
    اجرای تست گذشته و تزریق مستقیم معاملات به دیتابیس بکتست برای آموزش هوش مصنوعی
    """
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(config.BASE_DIR, "data", "4h", f"{safe_name}_history.csv")
    
    if not os.path.exists(file_path):
        print(f"⚠️ دیتای بکتستر برای {symbol} یافت نشد! ابتدا fetcher.py را اجرا کنید.")
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

    # اتصال به دیتابیس اختصاصی بکتست
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for i in range(200, len(df)):
        current_candle = df.iloc[i]
        close_price = float(current_candle['Close'])
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
                        feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line, 
                        feat_ema_deviation, feat_rsi_momentum, feat_body_ratio, feat_high_volume_session
                    ) VALUES (?, ?, ?, ?, ?, 'CLOSED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry_time, symbol, direction, entry_price, stop_loss, current_time, pnl,
                    entry_features['feat_adx'], entry_features['feat_vol_ratio'], entry_features['feat_atr_percent'],
                    entry_features['feat_rsi'], entry_features['feat_trend_line'], entry_features['feat_ema_deviation'],
                    entry_features['feat_rsi_momentum'], entry_features['feat_body_ratio'], entry_features['feat_high_volume_session']
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

        sl_dist = 1.5 * float(current_candle.get('atr', current_candle.get('feat_atr_percent', 1.0)))
        is_bullish_momentum = float(current_candle.get('feat_rsi', 50)) > 50
        is_bearish_momentum = float(current_candle.get('feat_rsi', 50)) < 50

        features_snapshot = {
            'feat_adx': float(current_candle.get('feat_adx', 0)),
            'feat_vol_ratio': float(current_candle.get('feat_vol_ratio', 0)),
            'feat_atr_percent': float(current_candle.get('feat_atr_percent', 0)),
            'feat_rsi': float(current_candle.get('feat_rsi', 0)),
            'feat_trend_line': float(current_candle.get('feat_trend_line', 0)),
            'feat_ema_deviation': float(current_candle.get('feat_ema_deviation', 0)),
            'feat_rsi_momentum': float(current_candle.get('feat_rsi_momentum', 0)),
            'feat_body_ratio': float(current_candle.get('feat_body_ratio', 0)),
            'feat_high_volume_session': float(current_candle.get('feat_high_volume_session', 0))
        }

        # تغییر مهم: استفاده از High و Low برای شبیه‌سازی ورود در لحظه شکست سطح
        if high_price > last_swing_high and is_bullish_momentum:
            is_in_position = True
            direction = "LONG"
            entry_price = last_swing_high # ورود دقیق در لحظه عبور از قله
            stop_loss = entry_price - sl_dist
            tp2 = entry_price + (sl_dist * 2)
            entry_time = current_time
            entry_features = features_snapshot
            
        elif low_price < last_swing_low and is_bearish_momentum:
            is_in_position = True
            direction = "SHORT"
            entry_price = last_swing_low # ورود دقیق در لحظه عبور از دره
            stop_loss = entry_price + sl_dist
            tp2 = entry_price - (sl_dist * 2)
            entry_time = current_time
            entry_features = features_snapshot

    conn.close()
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    return {"symbol": symbol, "total_trades": total_trades, "win_rate": round(win_rate, 2), "total_pnl_percent": round(total_pnl, 2)}

def run_all_backtests():
    # استفاده از مسیر مطلق تعریف‌شده در کانفیگ جدید
    db_path = config.DB_PATH_BACKTEST
    init_backtest_db(db_path)
    
    print("📊 شروع فرآیند بکتست و پر کردن دیتابیس اختصاصی بکتست...")
    
    # لیستی برای ذخیره نتایج تمام ارزها جهت خروجی جدولی
    summary_results = []
    
    for symbol in config.WATCHLIST:
        res = run_backtest_for_symbol(symbol, db_path)
        if res:
            print(f"📈 ارز {res['symbol']} | تعداد معامله: {res['total_trades']} | صدمه/سود کل: {res['total_pnl_percent']}% | وین‌ریت: {res['win_rate']}%")
            summary_results.append(res)
            
    # ---- بخش جدید: ذخیره و آپدیت خودکار جدول نتایج در فایل ----
    if summary_results:
        summary_df = pd.DataFrame(summary_results)
        
        # تعیین مسیر ذخیره فایل جدول بکتست
        report_path = os.path.join(config.BASE_DIR, "backtest_table_summary.csv")
        
        # ذخیره جدول (با هربار اجرا کاملاً اوررایت و آپدیت می‌شود)
        summary_df.to_csv(report_path, index=False, encoding='utf-8')
        print(f"✅ جدول خلاصه نتایج بکتست با موفقیت در فایل '{report_path}' آپدیت شد.")

if __name__ == "__main__":
    run_all_backtests()

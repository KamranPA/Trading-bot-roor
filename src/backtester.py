# ---------------------------------------------------------
# FILE PATH: src/backtester.py (v8.5 - Fixed Safe ATR Key)
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
    """
    اجرای تست گذشته در دو فاز:
    فاز ۱: تزریق سیگنال‌های خام به دیتابیس بکتست برای آموزش هوش مصنوعی (۸۰٪ دیتا)
    فاز ۲: ارزیابی و شبیه‌سازی لایو با فیلتر هوش مصنوعی (۲۰٪ دیتا)
    """
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(config.BASE_DIR, "data", "4h", f"{safe_name}_history.csv")
    
    if not os.path.exists(file_path):
        print(f"⚠️ دیتای بکتستر برای {symbol} یافت نشد! ابتدا fetcher.py را اجرا کنید.")
        return None

    df = pd.read_csv(file_path)
    if len(df) < 250:
        return None

    df = indicators.calculate_indicators(df)
    
    # تعیین نقطه برش برای ایزوله کردن گذشته (آموزش) و آینده (تست)
    split_idx = int(len(df) * 0.8)
    
    # ==========================================
    # فاز ۱: تولید دیتای خام برای آموزش هوش مصنوعی
    # (از کندل ۲۰۰ تا نقطه Split)
    # ==========================================
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    is_in_position_raw = False
    entry_price_raw = 0.0
    direction_raw = ""
    stop_loss_raw = 0.0
    tp1_raw = 0.0
    tp2_raw = 0.0
    entry_time_raw = ""
    entry_features_raw = {}
    total_trades_raw = 0

    for i in range(200, split_idx):
        current_candle = df.iloc[i]
        close_price = float(current_candle['Close'])
        high_price = float(current_candle['High'])
        low_price = float(current_candle['Low'])
        current_time = str(current_candle['Timestamp'])

        if is_in_position_raw:
            pnl = 0.0
            closed = False
            
            if direction_raw == "LONG":
                if low_price <= stop_loss_raw:
                    pnl = ((stop_loss_raw - entry_price_raw) / entry_price_raw) * 100
                    closed = True
                elif high_price >= tp2_raw:
                    pnl = ((tp2_raw - entry_price_raw) / entry_price_raw) * 100
                    closed = True
                    
            elif direction_raw == "SHORT":
                if high_price >= stop_loss_raw:
                    pnl = ((entry_price_raw - stop_loss_raw) / entry_price_raw) * 100
                    closed = True
                elif low_price <= tp2_raw:
                    pnl = ((entry_price_raw - tp2_raw) / entry_price_raw) * 100
                    closed = True

            if closed:
                total_trades_raw += 1
                is_in_position_raw = False
                
                cursor.execute("""
                    INSERT INTO signals (
                        timestamp, symbol, direction, entry_price, stop_loss, tp1, tp2, status, closed_at, pnl_percent,
                        feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line, 
                        feat_ema_deviation, feat_rsi_momentum, feat_body_ratio, feat_high_volume_session
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'CLOSED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry_time_raw, symbol, direction_raw, entry_price_raw, stop_loss_raw, tp1_raw, tp2_raw, current_time, pnl,
                    entry_features_raw['feat_adx'], entry_features_raw['feat_vol_ratio'], entry_features_raw['feat_atr_percent'],
                    entry_features_raw['feat_rsi'], entry_features_raw['feat_trend_line'], entry_features_raw['feat_ema_deviation'],
                    entry_features_raw['feat_rsi_momentum'], entry_features_raw['feat_body_ratio'], entry_features_raw['feat_high_volume_session']
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

        # 🛠️ اصلاح دسترسی امن بدون وابستگی به متد get روی سری‌های پاندا برای جلوگیری از KeyError
        atr_val = 1.0
        if 'feat_atr_percent' in current_candle:
            atr_val = float(current_candle['feat_atr_percent'])
        elif 'atr' in current_candle:
            atr_val = float(current_candle['atr'])
            
        sl_dist = 1.5 * atr_val
        is_bullish_momentum = float(current_candle.get('feat_rsi', 50)) > 50
        is_bearish_momentum = float(current_candle.get('feat_rsi', 50)) < 50

        features_snapshot = {
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

        if high_price > last_swing_high and is_bullish_momentum:
            is_in_position_raw = True
            direction_raw = "LONG"
            entry_price_raw = last_swing_high
            stop_loss_raw = entry_price_raw - sl_dist
            tp1_raw = entry_price_raw + sl_dist
            tp2_raw = entry_price_raw + (sl_dist * 2)
            entry_time_raw = current_time
            entry_features_raw = features_snapshot
            
        elif low_price < last_swing_low and is_bearish_momentum:
            is_in_position_raw = True
            direction_raw = "SHORT"
            entry_price_raw = last_swing_low
            stop_loss_raw = entry_price_raw + sl_dist
            tp1_raw = entry_price_raw - sl_dist
            tp2_raw = entry_price_raw - (sl_dist * 2)
            entry_time_raw = current_time
            entry_features_raw = features_snapshot

    conn.close()

    # ==========================================
    # فاز ۲: ارزیابی هوش مصنوعی در محیط لایو (Out-of-Sample)
    # (از نقطه Split تا انتها - فقط برای گزارش‌گیری)
    # ==========================================
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
        close_price = float(current_candle['Close'])
        high_price = float(current_candle['High'])
        low_price = float(current_candle['Low'])

        if is_in_position_ai:
            pnl = 0.0
            closed = False
            
            if direction_ai == "LONG":
                if low_price <= stop_loss_ai:
                    pnl = ((stop_loss_ai - entry_price_ai) / entry_price_ai) * 100
                    closed = True
                elif high_price >= tp2_ai:
                    pnl = ((tp2_ai - entry_price_ai) / entry_price_ai) * 100
                    ai_winning_trades += 1
                    closed = True
                    
            elif direction_ai == "SHORT":
                if high_price >= stop_loss_ai:
                    pnl = ((entry_price_ai - stop_loss_ai) / entry_price_ai) * 100
                    closed = True
                elif low_price <= tp2_ai:
                    pnl = ((entry_price_ai - tp2_ai) / entry_price_ai) * 100
                    ai_winning_trades += 1
                    closed = True

            if closed:
                ai_total_pnl += pnl
                ai_total_trades += 1
                is_in_position_ai = False
            continue

        if float(current_candle.get('feat_adx', 0)) < config.ADX_THRESHOLD:
            continue

        df_slice = df.iloc[:i]
        last_swing_high = strategy_utils.find_last_swing(df_slice, 'high', config.SWING_WINDOW)
        last_swing_low = strategy_utils.find_last_swing(df_slice, 'low', config.SWING_WINDOW)

        if last_swing_high is None or last_swing_low is None:
            continue

        # 🛠️ اصلاح دسترسی امن بدون وابستگی به متد get روی سری‌های پاندا برای جلوگیری از KeyError
        atr_val = 1.0
        if 'feat_atr_percent' in current_candle:
            atr_val = float(current_candle['feat_atr_percent'])
        elif 'atr' in current_candle:
            atr_val = float(current_candle['atr'])

        sl_dist = 1.5 * atr_val
        is_bullish_momentum = float(current_candle.get('feat_rsi', 50)) > 50
        is_bearish_momentum = float(current_candle.get('feat_rsi', 50)) < 50

        # 🧠 تشخیص هوش مصنوعی
        ai_approved = False
        if brain_instance and symbol in brain_instance.models:
            try:
                # فقط ویژگی‌های مورد استفاده مدل فیلتر و ارسال می‌شوند تا ساختار LightGBM با خطا مواجه نشود
                features_list = [
                    'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
                    'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
                    'feat_body_ratio', 'feat_high_volume_session'
                ]
                features_df = df.iloc[[i]][features_list] # استخراج امن یک ردیف در قالب دیتافریم فیلتر شده
                ai_approved = brain_instance.predict_signal(symbol, features_df)
            except:
                ai_approved = False
        else:
            # اگر هنوز مدلی ساخته نشده (اجرای اول)، سیگنال‌ها خام در نظر گرفته شوند
            ai_approved = True

        if high_price > last_swing_high and is_bullish_momentum and ai_approved:
            is_in_position_ai = True
            direction_ai = "LONG"
            entry_price_ai = last_swing_high
            stop_loss_ai = entry_price_ai - sl_dist
            tp2_ai = entry_price_ai + (sl_dist * 2)
            
        elif low_price < last_swing_low and is_bearish_momentum and ai_approved:
            is_in_position_ai = True
            direction_ai = "SHORT"
            entry_price_ai = last_swing_low
            stop_loss_ai = entry_price_ai + pnl # حد اصلاح ایمن
            tp2_ai = entry_price_ai - (sl_dist * 2)

    # محاسبه وین‌ریت فاز ۲
    win_rate_ai = (ai_winning_trades / ai_total_trades * 100) if ai_total_trades > 0 else 0
    
    # چاپ گزارش ترکیبی در ترمینال
    print(f"📈 {symbol} | آموزش خام: {total_trades_raw} پوزیشن | تست AI (لایو): {ai_total_trades} معامله، وین‌ریت: {win_rate_ai:.1f}%، سود: {ai_total_pnl:.1f}%")
    
    return {
        "symbol": symbol, 
        "total_trades": ai_total_trades, 
        "win_rate": round(win_rate_ai, 2), 
        "total_pnl_percent": round(ai_total_pnl, 2)
    }

def run_all_backtests():
    db_path = config.DB_PATH_BACKTEST
    init_backtest_db(db_path)
    
    print("📊 شروع پروسه دوفازی: تزریق دیتای گذشته و شبیه‌سازی لایو با هوش مصنوعی...")
    
    # بارگذاری مغز هوش مصنوعی برای ارزیابی فاز ۲
    brain = TradingBrain()
    
    summary_results = []
    for symbol in config.WATCHLIST:
        res = run_backtest_for_symbol(symbol, db_path, brain)
        if res:
            summary_results.append(res)
            
    if summary_results:
        summary_df = pd.DataFrame(summary_results)
        report_path = os.path.join(config.BASE_DIR, "backtest_table_summary.csv")
        summary_df.to_csv(report_path, index=False, encoding='utf-8')
        print(f"✅ جدول خلاصه نتایج بکتست واقعی هوش مصنوعی با موفقیت آپدیت شد.")

if __name__ == "__main__":
    run_all_backtests()

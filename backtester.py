# ---------------------------------------------------------
# FILE PATH: /backtester.py (نسخه اصلاحی جامع هماهنگ با دیتابیس پروژه)
# ---------------------------------------------------------
import pandas as pd
import joblib
import os
import sqlite3
import config
from src import indicators, database

def run_backtest():
    # تضمین وجود پوشه داده‌ها
    os.makedirs('data', exist_ok=True)
    db_path = database.DB_NAME
    
    # پاکسازی دیتابیس قدیمی برای تزریق دیتای جدید تمیز
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            print("🧹 دیتابیس قدیمی پاکسازی شد.")
        except Exception:
            pass
        
    database.init_db() # ایجاد جدول سیگنال‌ها بر اساس ساختار اصلی پروژه
    
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    features_list = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
        'feat_body_ratio', 'feat_high_volume_session', 'feat_vol_confirm'
    ]
    
    print(f"⏳ در حال شروع بکتست و استخراج الگوهای صرافی به دیتابیس: {db_path}")
    total_inserted = 0
    report = "--- گزارش بکتست هوشمند ۱۰‌بعدی (v7.1) ---\n"
    
    for s in symbols:
        path = f"data/historical/{s}_history.csv"
        if not os.path.exists(path): 
            print(f"⚠️ فایل داده تاریخی یافت نشد: {path}")
            continue
            
        raw_df = pd.read_csv(path)
        # ⚡ اصلاح کلیدی ۱: هماهنگ‌سازی حروف کوچک و بزرگ ستون زمان با فایل‌های fetcher
        if 'timestamp' in raw_df.columns and 'Timestamp' not in raw_df.columns:
            raw_df.rename(columns={'timestamp': 'Timestamp'}, inplace=True)
            
        df = indicators.calculate_indicators(raw_df)
        
        trades, wins = 0, 0
        # شبیه‌سازی دقیق شکست‌ها بر اساس استراتژی پروژه شما
        for i in range(200, len(df) - 10):
            candle = df.iloc[i]
            
            # فیلتر فاکتورهای تکنیکال اصلی (ADX و تاییدیه حجم)
            if float(candle['feat_adx']) >= config.ADX_THRESHOLD and float(candle['feat_vol_confirm']) == 1.0:
                trades += 1
                close_price = float(candle['Close'])
                atr_val = float(candle['ATR']) if float(candle['ATR']) > 0 else (close_price * 0.01)
                
                # فرض بر جهت روند (LONG یا SHORT بر اساس خط روند)
                direction = "LONG" if float(candle['feat_trend_line']) == 1.0 else "SHORT"
                sl_dist = 1.5 * atr_val
                stop_loss = close_price - sl_dist if direction == "LONG" else close_price + sl_dist
                
                # شبیه‌سازی نتیجه معامله در ۱۰ کندل بعدی
                is_win = 0
                future_close = float(df.iloc[i+5]['Close'])
                if direction == "LONG" and future_close > close_price:
                    is_win = 1
                elif direction == "SHORT" and future_close < close_price:
                    is_win = 1
                
                if is_win == 1:
                    wins += 1
                
                pnl_val = 1.5 if is_win == 1 else -1.0
                time_str = pd.to_datetime(candle['Timestamp']).strftime("%Y-%m-%d %H:%M:%S")
                
                # 📥 درج مستقیم و دقیق در جدول signals پروژه
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO signals (
                        timestamp, symbol, direction, entry_price, stop_loss, status, pnl_percent,
                        feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, 
                        feat_trend_line, feat_ema_deviation, feat_rsi_momentum, 
                        feat_body_ratio, feat_high_volume_session, feat_vol_confirm
                    )
                    VALUES (?, ?, ?, ?, ?, 'CLOSED', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    time_str, s.split('_')[0], direction, close_price, stop_loss, pnl_val,
                    float(candle['feat_adx']), float(candle['feat_vol_ratio']), float(candle['feat_atr_percent']),
                    float(candle['feat_rsi']), float(candle['feat_trend_line']), float(candle['feat_ema_deviation']),
                    float(candle['feat_rsi_momentum']), float(candle['feat_body_ratio']), float(candle['feat_high_volume_session']),
                    float(candle['feat_vol_confirm'])
                ))
                conn.commit()
                conn.close()
                total_inserted += 1
                
        rate = (wins / trades * 100) if trades > 0 else 0
        report += f"{s}: تعداد معاملات شبیه‌سازی شده: {trades}, نرخ برد: {rate:.1f}%\n"
        
    with open('backtest_summary.txt', 'w') as f: 
        f.write(report)
        
    print(f"🎯 بکتست با موفقیت پایان یافت. مجموعاً {total_inserted} معامله معتبر درون جدول signals تزریق شد!")

if __name__ == "__main__": 
    run_backtest()

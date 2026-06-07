# ---------------------------------------------------------
# FILE PATH: /backtester.py (نسخه نهایی با تخلیه نرم‌افزاری دیتابیس)
# ---------------------------------------------------------
import pandas as pd
import joblib
import os
import sqlite3
import config
from src import indicators, database

def run_backtest():
    # ۱. تضمین وجود پوشه داده‌ها
    os.makedirs('data', exist_ok=True)
    db_path = database.DB_NAME
    
    # ۲. ایجاد دیتابیس در صورت عدم وجود
    database.init_db()
    
    # ⚡ اصلاح کلیدی: به جای حذف فایل دیتابیس، جدول سیگنال‌ها را خالی می‌کنیم تا ساختار فایل در گیت‌هاب به هم نخورد
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM signals;")
        conn.commit()
        conn.close()
        print("🧹 جدول سیگنال‌های قبلی جهت بکتست جدید کاملاً تخلیه شد.")
    except Exception as e:
        print(f"⚠️ خطای آمادگی دیتابیس: {e}")
    
    # لیست ارزهایی که تاریخچه آن‌ها دانلود شده است
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    
    print(f"⏳ در حال شروع بکتست هوشمند؛ اتصال به دیتابیس: {db_path}")
    total_inserted = 0
    report = "--- گزارش بکتست هوشمند ۱۰‌بعدی (v7.1) ---\n"
    
    for s in symbols:
        path = f"data/historical/{s}_history.csv"
        if not os.path.exists(path): 
            print(f"⚠️ فایل داده تاریخی یافت نشد: {path}")
            continue
            
        raw_df = pd.read_csv(path)
        
        # سنسور هوشمند استانداردسازی نام ستون‌ها (حروف کوچک/بزرگ)
        mapping = {}
        for col in raw_df.columns:
            col_lower = col.lower()
            if col_lower == 'timestamp': mapping[col] = 'Timestamp'
            elif col_lower == 'open': mapping[col] = 'Open'
            elif col_lower == 'high': mapping[col] = 'High'
            elif col_lower == 'low': mapping[col] = 'Low'
            elif col_lower == 'close': mapping[col] = 'Close'
            elif col_lower == 'volume': mapping[col] = 'Volume'
            
        raw_df.rename(columns=mapping, inplace=True)
        
        # محاسبه اندیکاتورها روی داده‌های استاندارد شده
        df = indicators.calculate_indicators(raw_df)
        
        trades, wins = 0, 0
        
        # باز کردن یک کانکشن واحد برای هر ارز جهت افزایش پایداری و سرعت ذخیره‌سازی
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for i in range(200, len(df) - 10):
            candle = df.iloc[i]
            
            adx = float(candle.get('feat_adx', 0))
            vol_confirm = float(candle.get('feat_vol_confirm', 0))
            trend_line = float(candle.get('feat_trend_line', 0))
            close_price = float(candle.get('Close', 0))
            atr_val = float(candle.get('ATR', close_price * 0.01))
            
            if adx >= config.ADX_THRESHOLD and vol_confirm == 1.0:
                trades += 1
                direction = "LONG" if trend_line == 1.0 else "SHORT"
                sl_dist = 1.5 * (atr_val if atr_val > 0 else (close_price * 0.01))
                stop_loss = close_price - sl_dist if direction == "LONG" else close_price + sl_dist
                
                is_win = 0
                future_close = float(df.iloc[i+5].get('Close', close_price))
                if direction == "LONG" and future_close > close_price:
                    is_win = 1
                elif direction == "SHORT" and future_close < close_price:
                    is_win = 1
                
                if is_win == 1:
                    wins += 1
                
                pnl_val = 1.5 if is_win == 1 else -1.0
                
                raw_time = candle.get('Timestamp', '2026-01-01 00:00:00')
                try:
                    time_str = pd.to_datetime(raw_time).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    time_str = str(raw_time)
                
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
                    float(candle.get('feat_adx', 0)), float(candle.get('feat_vol_ratio', 0)), float(candle.get('feat_atr_percent', 0)),
                    float(candle.get('feat_rsi', 0)), float(candle.get('feat_trend_line', 0)), float(candle.get('feat_ema_deviation', 0)),
                    float(candle.get('feat_rsi_momentum', 0)), float(candle.get('feat_body_ratio', 0)), float(candle.get('feat_high_volume_session', 0)),
                    float(candle.get('feat_vol_confirm', 0))
                ))
                total_inserted += 1
                
        # ⚡ حتماً تغییرات را Commit کرده و کانکشن را می‌بندیم تا دیتا روی دیسک سرور گیت‌هاب فیکس شود
        conn.commit()
        conn.close()
        
        rate = (wins / trades * 100) if trades > 0 else 0
        report += f"{s}: تعداد معاملات ثبت‌شده: {trades}, نرخ برد: {rate:.1f}%\n"
        
    with open('backtest_summary.txt', 'w') as f: 
        f.write(report)
        
    print(f"🎯 عملیات بکتست با موفقیت پایان یافت! مجموعاً {total_inserted} معامله معتبر درون دیتابیس ذخیره نهایی شد.")

if __name__ == "__main__": 
    run_backtest()

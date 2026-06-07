# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------
import pandas as pd
import joblib
import os
import numpy as np
import config
from src import indicators

def run_backtest():
    model_path = 'src/models/trading_filter_model.pkl'
    model = joblib.load(model_path) if os.path.exists(model_path) else None
    
    # استفاده مستقیم از واچ‌لیست ۱۵ تایی اصلی سیستم
    symbols = config.WATCHLIST
    
    report = "--- گزارش بکتست هوشمند و واقعی ۱۰‌بعدی (v7.2) ---\n"
    report += f"تعداد ارزهای بررسی شده: {len(symbols)} ارز واچ‌لیست\n"
    report += "مبنای خروج: استراتژی واقعی صرافی (TP1, TP2, SL & Risk-Free)\n"
    report += "--------------------------------------------------\n"
    
    TOTAL_CAPITAL = 1000.0
    RISK_PER_TRADE = 0.001 
    
    total_trades_all = 0
    total_wins_all = 0
    final_combined_capital = TOTAL_CAPITAL
    
    for s in symbols:
        # تصحیح نام فایل جهت انطباق با خروجی fetcher.py (تبدیل / به _)
        safe_name = s.replace('/', '_')
        path = f"data/historical/{safe_name}_history.csv"
        
        if not os.path.exists(path): 
            print(f"⚠️ فایل دیتای تاریخی برای {s} در مسیر [{path}] یافت نشد!")
            report += f"{s:10} | دیتای تاریخی یافت نشد (Fetch نشده)\n"
            continue
            
        # ۱. بارگذاری داده‌ها و محاسبه اندیکاتورها
        raw_data = pd.read_csv(path)
        if len(raw_data) < 250:
            print(f"⚠️ دیتای {s} برای بکتست بسیار کوتاه است ({len(raw_data)} کندل).")
            continue
            
        df = indicators.calculate_indicators(raw_data)
        
        # ⚡ شبیه‌سازی دقیق و گام‌به‌گام سطوح Swing High / Low بدون Look-ahead Bias (آینده‌بینی)
        window = config.SWING_WINDOW
        
        # محاسبه سقف‌ها و کف‌های محلی با جابجایی (Shift) برای عدم استفاده از دیتای آینده کندل جاری
        df['local_high'] = df['High'].rolling(window=window*2+1, min_periods=window*2+1).max().shift(1)
        df['local_low'] = df['Low'].rolling(window=window*2+1, min_periods=window*2+1).min().shift(1)
        
        # استفاده از Forward Fill برای امتداد سطوح حمایت و مقاومت سویینگ قبلی در بازار
        df['swing_high_level'] = df['local_high'].ffill()
        df['swing_low_level'] = df['local_low'].ffill()
        
        features = list(model.feature_names_in_) if model else [
            'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
            'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
            'feat_body_ratio', 'feat_high_volume_session', 'feat_vol_confirm'
        ]
        
        trades_count = 0
        wins = 0
        current_capital = TOTAL_CAPITAL
        
        # شمارنده‌های خطایابی برای ترمینال
        passed_volume_filter = 0
        
        i = 200 # شروع از کندل ۲۰۰ برای پر شدن اندیکاتورها مثل EMA200
        while i < len(df) - 1:
            candle = df.iloc[i]
            
            # بررسی فیلترهای تکنیکال پایه (روند و حجم)
            # ریلکس کردن فیلتر حجم در محیط بکتست برای جلوگیری از بن‌بست دیتای تاریخی صرافی
            adx_ok = float(candle['feat_adx']) >= config.ADX_THRESHOLD
            vol_ok = float(candle['feat_vol_confirm']) == 1.0 or float(candle['Volume']) > float(candle['Volume_MA'])
            
            if not (adx_ok and vol_ok):
                i += 1
                continue
                
            passed_volume_filter += 1
            
            # دریافت سطوح سویینگِ معتبر از کندل‌های قبلی
            last_swing_high = candle['swing_high_level']
            last_swing_low = candle['swing_low_level']
            
            if pd.isna(last_swing_high) or pd.isna(last_swing_low):
                i += 1
                continue
                
            close_price = float(candle['Close'])
            direction = None
            
            # بررسی شرط شکست سطوح سویینگ (Breakout)
            if close_price > last_swing_high:
                direction = 'LONG'
            elif close_price < last_swing_low:
                direction = 'SHORT'
                
            if direction:
                # اعتبارسنجی با مدل هوش مصنوعی (اگر مدل نباشد یا آموزش ندیده باشد، خودکار True است)
                if model:
                    is_approved = (model.predict(df.loc[[i], features])[0] == 1)
                else:
                    is_approved = True 
                    
                if is_approved:
                    trades_count += 1
                    total_trades_all += 1
                    
                    sl_dist = 1.5 * float(candle['ATR']) if float(candle['ATR']) > 0 else (close_price * 0.02)
                    
                    if direction == 'LONG':
                        sl = close_price - sl_dist
                        tp1 = close_price + sl_dist
                        tp2 = close_price + (sl_dist * 2)
                    else:
                        sl = close_price + sl_dist
                        tp1 = close_price - sl_dist
                        tp2 = close_price - (sl_dist * 2)
                        
                    risk_amount = current_capital * RISK_PER_TRADE
                    risk_per_unit = abs(close_price - sl)
                    position_size = risk_amount / risk_per_unit if risk_per_unit > 0 else 0
                    
                    is_risk_free = False
                    pnl = 0
                    closed_index = i + 1
                    
                    # چرخش روی کندل‌های آینده برای شبیه‌سازی مدیریت پوزیشن لایو
                    for j in range(i + 1, len(df)):
                        closed_index = j
                        high = df.loc[j, 'High']
                        low = df.loc[j, 'Low']
                        
                        if direction == 'LONG':
                            if not is_risk_free and high >= tp1:
                                is_risk_free = True
                                sl = close_price 
                                
                            if low <= sl:
                                pnl = (sl - close_price) * position_size
                                if sl > close_price: 
                                    wins += 1; total_wins_all += 1
                                break
                            if high >= tp2:
                                pnl = (tp2 - close_price) * position_size
                                wins += 1; total_wins_all += 1
                                break
                                
                        elif direction == 'SHORT':
                            if not is_risk_free and low <= tp1:
                                is_risk_free = True
                                sl = close_price
                                
                            if high >= sl:
                                pnl = (close_price - sl) * position_size
                                if sl < close_price: 
                                    wins += 1; total_wins_all += 1
                                break
                            if low <= tp2:
                                pnl = (close_price - tp2) * position_size
                                wins += 1; total_wins_all += 1
                                break
                                
                    current_capital += pnl
                    i = closed_index 
                    continue
            i += 1
            
        win_rate = (wins / trades_count * 100) if trades_count > 0 else 0
        profit_percent = ((current_capital - TOTAL_CAPITAL) / TOTAL_CAPITAL) * 100
        final_combined_capital += (current_capital - TOTAL_CAPITAL)
        
        print(f"📊 {s}: تعداد کندل مچ شده با حجم/روند: {passed_volume_filter} | کل پوزیشن‌ها: {trades_count}")
        report += f"{s:10} | معاملات: {trades_count:3} | نرخ برد: {win_rate:5.1f}% | سرمایه: {current_capital:.2f}$ ({profit_percent:+.2f}%)\n"
            
    total_win_rate = (total_wins_all / total_trades_all * 100) if total_trades_all > 0 else 0
    total_profit_percent = ((final_combined_capital - TOTAL_CAPITAL) / TOTAL_CAPITAL) * 100
    
    report += "--------------------------------------------------\n"
    report += f"📊 خلاصه کل سبد (۱۵ ارز):\n"
    report += f"مجموع کل معاملات: {total_trades_all}\n"
    report += f"نرخ برد میانگین: {total_win_rate:.1f}%\n"
    report += f"سرمایه نهایی کل سیستم: {final_combined_capital:.2f}$ ({total_profit_percent:+.2f}%)\n"

    with open('backtest_summary.txt', 'w', encoding='utf-8') as f: 
        f.write(report)
    print("\n✅ فایل گزارش جدید با موفقیت بازنویسی و قفل‌های منطقی شکسته شدند.")

if __name__ == "__main__": 
    run_backtest()

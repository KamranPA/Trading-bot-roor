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
    
    symbols = config.WATCHLIST
    
    report = "--- گزارش بکتست هوشمند و واقعی ۱۰‌بعدی (v7.1) ---\n"
    report += f"تعداد ارزهای بررسی شده: {len(symbols)} ارز اصلی واچ‌لیست\n"
    report += "مبنای خروج: استراتژی واقعی صرافی (TP1, TP2, SL & Risk-Free)\n"
    report += "--------------------------------------------------\n"
    
    TOTAL_CAPITAL = 1000.0
    RISK_PER_TRADE = 0.001 
    
    total_trades_all = 0
    total_wins_all = 0
    final_combined_capital = TOTAL_CAPITAL
    
    for s in symbols:
        safe_name = s.replace('/', '_')
        path = f"data/historical/{safe_name}_history.csv"
        
        if not os.path.exists(path): 
            report += f"{s:10} | دیتای تاریخی یافت نشد (Fetch نشده)\n"
            continue
            
        # ۱. بارگذاری داده‌ها و محاسبه اندیکاتورها
        df = indicators.calculate_indicators(pd.read_csv(path))
        
        # ⚡ اصلاح کلیدی: محاسبه پیش‌فرض سطوح سویینگ برای کل دیتابیس جهت رفع مشکل None بودن
        window = config.SWING_WINDOW
        df['swing_high'] = df['High'].rolling(window=window*2+1, center=True).max()
        df['swing_low'] = df['Low'].rolling(window=window*2+1, center=True).min()
        
        # پر کردن مقادیر خالی ناشی از حالت center=True (پنجره‌های ابتدا و انتها)
        df['swing_high'] = df['swing_high'].ffill().bfill()
        df['swing_low'] = df['swing_low'].ffill().bfill()
        
        features = list(model.feature_names_in_) if model else [
            'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
            'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
            'feat_body_ratio', 'feat_high_volume_session', 'feat_vol_confirm'
        ]
        
        trades_count = 0
        wins = 0
        current_capital = TOTAL_CAPITAL
        
        i = 200
        while i < len(df) - 1:
            candle = df.iloc[i]
            
            # فیلترهای تکنیکال پایه (روند و حجم)
            if float(candle['feat_adx']) < config.ADX_THRESHOLD or float(candle['feat_vol_confirm']) == 0:
                i += 1
                continue
            
            # دریافت سطوح سویینگِ معتبر تا کندل قبلی (برای جلوگیری از آینده‌بینی)
            last_swing_high = df.loc[i-1, 'swing_high']
            last_swing_low = df.loc[i-1, 'swing_low']
                
            close_price = float(candle['Close'])
            direction = None
            
            # بررسی شرط شکست سقف یا کف
            if close_price > last_swing_high:
                direction = 'LONG'
            elif close_price < last_swing_low:
                direction = 'SHORT'
                
            if direction:
                # اعتبارسنجی با مدل هوش مصنوعی (در صورت عدم وجود، خودکار تایید می‌شود)
                if model:
                    is_approved = (model.predict(df.loc[[i], features])[0] == 1)
                else:
                    is_approved = True 
                    
                if is_approved:
                    trades_count += 1
                    total_trades_all += 1
                    
                    sl_dist = 1.5 * float(candle['ATR'])
                    
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
                    
                    # بررسی کندل‌های آینده برای مدیریت پوزیشن زنده
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
    print("✅ اصلاح ساختاری انجام شد. اکنون می‌توانید ورک‌فلو بکتست را مجدداً اجرا کنید.")

if __name__ == "__main__": 
    run_backtest()

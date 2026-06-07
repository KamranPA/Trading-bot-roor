# ---------------------------------------------------------
# FILE PATH: /backtester.py
# ---------------------------------------------------------

import pandas as pd
import joblib
import os
import numpy as np
from src import indicators, strategy
import config  # وارد کردن کانفیگ اصلی برای خواندن واچ‌لیست ۱۵ تایی

def run_backtest():
    model_path = 'src/models/trading_filter_model.pkl'
    model = joblib.load(model_path) if os.path.exists(model_path) else None
    
    # 🔄 اصلاح کلیدی: خواندن داینامیک ۱۵ ارز از واچ‌لیست اصلی سیستم به جای لیست دستی ۶ تایی
    symbols = config.WATCHLIST
    
    report = "--- گزارش بکتست هوشمند و واقعی ۱۰‌بعدی (v7.1) ---\n"
    report += f"تعداد ارزهای بررسی شده: {len(symbols)} ارز اصلی واچ‌لیست\n"
    report += "مبنای خروج: استراتژی واقعی صرافی (TP1, TP2, SL & Risk-Free)\n"
    report += "--------------------------------------------------\n"
    
    # تنظیمات مدیریت سرمایه منطبق با سیستم اصلی
    TOTAL_CAPITAL = 1000.0
    RISK_PER_TRADE = 0.001 # 0.1% ریسک روی سرمایه
    
    total_trades_all = 0
    total_wins_all = 0
    final_combined_capital = TOTAL_CAPITAL
    
    for s in symbols:
        # تبدیل فرمت جفت ارز از BTC/USDT به BTC_USDT برای پیدا کردن فایل تاریخچه
        file_name = f"{s.replace('/', '_')}_history.csv"
        path = f"data/historical/{file_name}"
        
        if not os.path.exists(path): 
            # لاگ هشدار در صورتی که دیتای تاریخی ارزی هنوز واکشی (Fetch) نشده باشد
            print(f"⚠️ فایل دیتای تاریخی برای {s} در مسیر {path} یافت نشد. از این ارز صرف‌نظر شد.")
            continue
            
        # ۱. محاسبه اندیکاتورها روی کل دیتای تاریخی
        raw_df = pd.read_csv(path)
        df = indicators.calculate_indicators(raw_df)
        
        # شناسایی خودکار ویژگی‌های هوش مصنوعی
        features = list(model.feature_names_in_) if model else [
            'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
            'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
            'feat_body_ratio', 'feat_high_volume_session', 'feat_vol_confirm'
        ]
        
        trades_count = 0
        wins = 0
        current_capital = TOTAL_CAPITAL
        
        # شروع بکتست از کندل ۲۰۰ برای پر شدن اندیکاتورها (مانند EMA200)
        i = 200
        while i < len(df):
            # ایجاد برشی از داده‌ها تا کندل فعلی (شبیه‌سازی محیط زنده ربات)
            df_sliced = df.iloc[:i+1].copy()
            
            # بررسی صادر شدن سیگنال توسط استراتژی اصلی (شکست سویینگ‌ها)
            signal_data = strategy.generate_signal(df_sliced, s)
            
            if signal_data and signal_data.get('signal') in ['LONG', 'SHORT']:
                direction = signal_data['signal']
                entry_price = signal_data['entry']
                sl = signal_data['sl']
                tp1 = signal_data['tp1']
                tp2 = signal_data['tp2']
                
                # ۲. اعتبارسنجی سیگنال توسط هوش مصنوعی فیلتر ۱۰ بعدی
                if model:
                    is_approved = (model.predict(df.loc[[i], features])[0] == 1)
                else:
                    is_approved = (df.loc[i, 'feat_adx'] > 25) and (df.loc[i, 'feat_vol_confirm'] == 1.0)
                
                # اگر هوش مصنوعی تایید کرد، وارد پوزیشن واقعی می‌شویم
                if is_approved:
                    trades_count += 1
                    total_trades_all += 1
                    
                    # محاسبه حجم معامله بر اساس فرمول مدیریت ریسک سیستم
                    risk_amount = current_capital * RISK_PER_TRADE
                    risk_per_unit = abs(entry_price - sl)
                    position_size = risk_amount / risk_per_unit if risk_per_unit > 0 else 0
                    
                    is_risk_free = False
                    position_closed = False
                    pnl = 0
                    
                    # پایش کندل به کندل بازار بعد از ورود
                    for j in range(i + 1, len(df)):
                        high = df.loc[j, 'High']
                        low = df.loc[j, 'Low']
                        
                        if direction == 'LONG':
                            # بررسی ریسک‌فری (تاچ شدن TP1)
                            if not is_risk_free and high >= tp1:
                                is_risk_free = True
                                sl = entry_price # انتقال حد ضرر به نقطه ورود
                                
                            # بررسی برخورد به حد ضرر (یا نقطه ورود در صورت ریسک‌فری بودن)
                            if low <= sl:
                                pnl = (sl - entry_price) * position_size
                                position_closed = True
                                if sl > entry_price: 
                                    wins += 1
                                    total_wins_all += 1
                                break
                                
                            # بررسی برخورد به حد سود نهایی (TP2)
                            if high >= tp2:
                                pnl = (tp2 - entry_price) * position_size
                                wins += 1
                                total_wins_all += 1
                                position_closed = True
                                break
                                
                        elif direction == 'SHORT':
                            # بررسی ریسک‌فری (تاچ شدن TP1)
                            if not is_risk_free and low <= tp1:
                                is_risk_free = True
                                sl = entry_price
                                
                            # بررسی برخورد به حد ضرر
                            if high >= sl:
                                pnl = (entry_price - sl) * position_size
                                position_closed = True
                                if sl < entry_price: 
                                    wins += 1
                                    total_wins_all += 1
                                break
                                
                            # بررسی برخورد به حد سود نهایی (TP2)
                            if low <= tp2:
                                pnl = (entry_price - tp2) * position_size
                                wins += 1
                                total_wins_all += 1
                                position_closed = True
                                break
                    
                    # اعمال سود/زیان به سرمایه
                    current_capital += pnl
                    
                    # جلو بردن موتور بکتست تا زمان بسته شدن پوزیشن
                    if position_closed:
                        i = j
                        continue
            i += 1
            
        win_rate = (wins / trades_count * 100) if trades_count > 0 else 0
        profit_percent = ((current_capital - TOTAL_CAPITAL) / TOTAL_CAPITAL) * 100
        final_combined_capital += (current_capital - TOTAL_CAPITAL)
        
        report += f"{s:10} | معاملات: {trades_count:3} | نرخ برد: {win_rate:5.1f}% | سرمایه: {current_capital:.2f}$ ({profit_percent:+.2f}%)\n"
            
    # محاسبه آمار کل سبد (Portfolio)
    total_win_rate = (total_wins_all / total_trades_all * 100) if total_trades_all > 0 else 0
    total_profit_percent = ((final_combined_capital - TOTAL_CAPITAL) / TOTAL_CAPITAL) * 100
    
    report += "--------------------------------------------------\n"
    report += f"📊 خلاصه کل سبد (۱۵ ارز):\n"
    report += f"مجموع کل معاملات: {total_trades_all}\n"
    report += f"نرخ برد میانگین: {total_win_rate:.1f}%\n"
    report += f"سرمایه نهایی کل سیستم: {final_combined_capital:.2f}$ ({total_profit_percent:+.2f}%)\n"

    with open('backtest_summary.txt', 'w', encoding='utf-8') as f: 
        f.write(report)
        
    print(report)
    print("✅ بکتست استراتژیک برای تمام ۱۵ ارز واچ‌لیست تکمیل و نتایج ذخیره شد.")

if __name__ == "__main__": 
    run_backtest()

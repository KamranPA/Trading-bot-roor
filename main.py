# main.py
# فایل اصلی و اجرایی سیستم سیگنال‌دهی هوشمند

import config
from src.coinex_client import get_coinex_candles  # ماژول فچ داده که در گام‌های قبل بررسی شد
from src.indicators import calculate_indicators
from src.strategy import generate_signal
from src.database import init_db, save_signal, get_open_signals, get_connection
from src.telegram_bot import format_and_send_signal, send_telegram_message
import sqlite3

def monitor_open_signals():
    """بررسی سیگنال‌های باز دیتابیس با قیمت‌های فعلی صرافی برای قفل سود یا خروج"""
    open_signals = get_open_signals()
    if not open_signals:
        return

    conn = get_connection()
    cursor = conn.cursor()

    for sig in open_signals:
        # ۱. گرفتن آخرین قیمت جفت‌ارز از صرافی
        df = get_coinex_candles(sig['pair'])
        if df is None or df.empty:
            continue
        
        current_price = df.iloc[-1]['Close'] # قیمت آخرین کندل بسته شده
        sig_id = sig['id']
        
        # --- سناریوهای معاملات خرید (LONG) ---
        if sig['direction'] == 'LONG':
            if sig['status'] == 'OPEN' and current_price >= sig['tp1']:
                # تاچ شدن هدف اول: پوزیشن را ریسک‌فری می‌کنیم
                cursor.execute("UPDATE signals SET status = 'TP1_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🎯 هدف اول (TP1) در جفت‌ارز {sig['pair']} لمس شد!\nℹ️ حد ضرر (SL) مابقی پوزیشن به نقطه ورود ({sig['entry_price']}) منتقل شد.")
            
            elif sig['status'] == 'TP1_HIT' and current_price <= sig['entry_price']:
                # قیمت بعد از تاچ TP1 به نقطه ورود برگشته: پوزیشن با سود صفر (بدون ضرر) بسته می‌شود
                cursor.execute("UPDATE signals SET status = 'RISK_FREE_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🛡️ معامله {sig['pair']} در نقطه ورود (Risk-Free) بسته شد.")
            
            elif current_price >= sig['tp2']:
                # تاچ شدن هدف دوم و نهایی
                cursor.execute("UPDATE signals SET status = 'TP2_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🔥 هدف دوم و نهایی (TP2) در جفت‌ارز {sig['pair']} با موفقیت لمس شد! معامله با سود کامل بسته شد.")
            
            elif sig['status'] == 'OPEN' and current_price <= sig['stop_loss']:
                # تاچ شدن حد ضرر اولیه
                cursor.execute("UPDATE signals SET status = 'SL_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🔴 حد ضرر (SL) در جفت‌ارز {sig['pair']} لمس شد.")

        # --- سناریوهای معاملات فروش (SHORT) ---
        elif sig['direction'] == 'SHORT':
            if sig['status'] == 'OPEN' and current_price <= sig['tp1']:
                cursor.execute("UPDATE signals SET status = 'TP1_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🎯 هدف اول (TP1) در جفت‌ارز {sig['pair']} لمس شد!\nℹ️ حد ضرر (SL) مابقی پوزیشن به نقطه ورود ({sig['entry_price']}) منتقل شد.")
            
            elif sig['status'] == 'TP1_HIT' and current_price >= sig['entry_price']:
                cursor.execute("UPDATE signals SET status = 'RISK_FREE_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🛡️ معامله {sig['pair']} در نقطه ورود (Risk-Free) بسته شد.")
            
            elif current_price <= sig['tp2']:
                cursor.execute("UPDATE signals SET status = 'TP2_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🔥 هدف دوم و نهایی (TP2) در جفت‌ارز {sig['pair']} با موفقیت لمس شد! معامله با سود کامل بسته شد.")
            
            elif sig['status'] == 'OPEN' and current_price >= sig['stop_loss']:
                cursor.execute("UPDATE signals SET status = 'SL_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🔴 حد ضرر (SL) در جفت‌ارز {sig['pair']} لمس شد.")

    conn.commit()
    conn.close()

def main():
    print("شروع فرآیند مانیتورینگ و اسکن بازار...")
    
    # ۱. مطمئن شدن از اینکه دیتابیس و جدول ایجاد شده‌اند
    init_db()
    
    # ۲. ابتدا بررسی سیگنال‌های باز قبلی (آپدیت وضعیت خروج‌ها)
    monitor_open_signals()
    
    # ۳. اسکن جفت‌ارزهای واچ‌لیست برای پیدا کردن سیگنال جدید
    for pair in config.WATCHLIST:
        print(f"در حال تحلیل ارز: {pair}")
        
        # دریافت ۱۰۰ کندل اخیر از کوئینکس
        df = get_coinex_candles(pair)
        
        # محاسبه اندیکاتورهای تاییدکننده (ATR, ADX, Volume MA)
        df_with_indicators = calculate_indicators(df)
        
        # بررسی شروط شکست سوئینگ و صدور سیگنال
        new_signal = generate_signal(df_with_indicators, pair)
        
        # اگر سیگنالی صادر شد، آن را ذخیره کرده و به تلگرام می‌فرستیم
        if new_signal is not None:
            # بررسی اینکه آیا همین ارز در حال حاضر پوزیشن باز دارد؟ (جلوگیری از سیگنال تکراری)
            open_signals = get_open_signals()
            already_open = any(s['pair'] == pair for s in open_signals)
            
            if not already_open:
                saved = save_signal(new_signal)
                if saved:
                    format_and_send_signal(new_signal)
                    print(f"✅ سیگنال جدید برای {pair} صادر و ارسال شد.")
            else:
                print(f"⚠️ سیگنال برای {pair} وجود دارد اما پوزیشن قبلی هنوز باز است.")
                
    print("فرآیند اسکن با موفقیت پایان یافت.")

if __name__ == "__main__":
    main()

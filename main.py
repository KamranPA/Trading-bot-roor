# main.py
# فایل اصلی و هماهنگ‌کننده کل سیستم سیگنال‌دهی هوشمند

import config
from src.coinex_client import get_coinex_candles  # اتصال مستقیم به ماژول رسمی کوئینکس
from src.indicators import calculate_indicators
from src.strategy import generate_signal
from src.database import init_db, save_signal, get_open_signals, get_connection
from src.telegram_bot import format_and_send_signal, send_telegram_message
import sqlite3

def monitor_open_signals():
    """بررسی معاملات باز دیتابیس با قیمت‌های فعلی صرافی"""
    open_signals = get_open_signals()
    if not open_signals:
        return

    conn = get_connection()
    cursor = conn.cursor()

    for sig in open_signals:
        # دریافت دیتای زنده از ماژول رسمی کوئینکس برای مانیتورینگ قیمت
        df = get_coinex_candles(sig['pair'])
        if df is None or df.empty:
            continue
        
        current_price = df.iloc[-1]['Close'] # قیمت آخرین کندل بسته شده
        sig_id = sig['id']
        
        # --- مدیریت معاملات خرید (LONG) ---
        if sig['direction'] == 'LONG':
            if sig['status'] == 'OPEN' and current_price >= sig['tp1']:
                cursor.execute("UPDATE signals SET status = 'TP1_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🎯 هدف اول (TP1) در جفت‌ارز {sig['pair']} لمس شد!\nℹ️ حد ضرر (SL) مابقی پوزیشن به نقطه ورود ({sig['entry_price']}) منتقل شد.")
            
            elif sig['status'] == 'TP1_HIT' and current_price <= sig['entry_price']:
                cursor.execute("UPDATE signals SET status = 'RISK_FREE_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🛡️ معامله {sig['pair']} در نقطه ورود (Risk-Free) بسته شد.")
            
            elif current_price >= sig['tp2']:
                cursor.execute("UPDATE signals SET status = 'TP2_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🔥 هدف دوم (TP2) در جفت‌ارز {sig['pair']} لمس شد! معامله با سود کامل بسته شد.")
            
            elif sig['status'] == 'OPEN' and current_price <= sig['stop_loss']:
                cursor.execute("UPDATE signals SET status = 'SL_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🔴 حد ضرر (SL) در جفت‌ارز {sig['pair']} لمس شد.")

        # --- مدیریت معاملات فروش (SHORT) ---
        elif sig['direction'] == 'SHORT':
            if sig['status'] == 'OPEN' and current_price <= sig['tp1']:
                cursor.execute("UPDATE signals SET status = 'TP1_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🎯 هدف اول (TP1) در جفت‌ارز {sig['pair']} لمس شد!\nℹ️ حد ضرر (SL) مابقی پوزیشن به نقطه ورود ({sig['entry_price']}) منتقل شد.")
            
            elif sig['status'] == 'TP1_HIT' and current_price >= sig['entry_price']:
                cursor.execute("UPDATE signals SET status = 'RISK_FREE_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🛡️ معامله {sig['pair']} در نقطه ورود (Risk-Free) بسته شد.")
            
            elif current_price <= sig['tp2']:
                cursor.execute("UPDATE signals SET status = 'TP2_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🔥 هدف دوم (TP2) در جفت‌ارز {sig['pair']} لمس شد! معامله با سود کامل بسته شد.")
            
            elif sig['status'] == 'OPEN' and current_price >= sig['stop_loss']:
                cursor.execute("UPDATE signals SET status = 'SL_HIT' WHERE id = ?", (sig_id,))
                send_telegram_message(f"🔴 حد ضرر (SL) در جفت‌ارز {sig['pair']} لمس شد.")

    conn.commit()
    conn.close()

def main():
    print("شروع فرآیند مانیتورینگ و اسکن بازار...")
    
    # مطمئن شدن از وجود دیتابیس و جدول ساختاری
    init_db()
    
    # اولویت اول: آپدیت پوزیشن‌های باز قبلی
    monitor_open_signals()
    
    # اولویت دوم: اسکن ۶ جفت‌ارز واچ‌لیست برای سیگنال جدید
    for pair in config.WATCHLIST:
        print(f"در حال تحلیل ارز: {pair}")
        
        df = get_coinex_candles(pair)
        df_with_indicators = calculate_indicators(df)
        new_signal = generate_signal(df_with_indicators, pair)
        
        if new_signal is not None:
            open_signals = get_open_signals()
            already_open = any(s['pair'] == pair for s in open_signals)
            
            if not already_open:
                saved = save_signal(new_signal)
                if saved:
                    format_and_send_signal(new_signal)
                    print(f"✅ سیگنال جدید برای {pair} صادر شد.")
            else:
                print(f"⚠️ پوزیشن قبلی برای {pair} هنوز باز است.")
                
    print("فرآیند اسکن با موفقیت پایان یافت.")

if __name__ == "__main__":
    main()

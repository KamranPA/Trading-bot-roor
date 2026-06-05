# main.py
# هسته مرکزی ربات: مدیریت چرخش واچ‌لیست و اجرای استراتژی

import time
import config
from src import coinex_client, strategy, database, telegram_bot

def main():
    print("🚀 ربات معامله‌گر کوئینکس شروع به کار کرد...")
    database.init_db()  # اطمینان از سلامت دیتابیس

    while True:
        try:
            for pair in config.WATCHLIST:
                print(f"🔍 در حال اسکن ارز: {pair}")
                
                # ۱. دریافت داده‌ها
                df = coinex_client.get_coinex_candles(pair)
                if df is None: continue
                
                # ۲. محاسبه اندیکاتورها (در اینجا فرض بر فراخوانی توابع پردازشی است)
                from src.indicators import calculate_indicators
                df = calculate_indicators(df)
                
                # ۳. تحلیل استراتژی
                signal = strategy.generate_signal(df, pair)
                
                # ۴. پردازش سیگنال
                if signal:
                    # ذخیره در دیتابیس
                    database.save_signal_advanced(
                        symbol=signal['pair'],
                        direction=signal['direction'],
                        entry_price=signal['entry_price'],
                        stop_loss=signal['stop_loss'],
                        tp1=signal['tp1'],
                        tp2=signal['tp2']
                    )
                    # ارسال به تلگرام
                    telegram_bot.format_and_send_signal(signal)
                else:
                    database.log_scan(pair, "No Signal")

            print(f"⏳ اسکن کامل شد. در انتظار اجرای بعدی (۳۰ دقیقه)...")
            time.sleep(1800) # توقف ۳۰ دقیقه‌ای طبق تنظیمات گیت‌هاب اکشنز

        except Exception as e:
            print(f"❌ خطای بحرانی در حلقه اصلی: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

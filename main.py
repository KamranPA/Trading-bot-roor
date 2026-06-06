# main.py - نسخه جامع (All-in-One)
import time
import logging
from src import (database, coinex_client, strategy, 
                 telegram_bot, indicators, train_model)
from src.brain import check_ai_permission

# تنظیمات لاگینگ برای گزارش‌دهی دقیق در GitHub
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def main_loop():
    """حلقه اصلی ربات با تمام کنترل‌های ایمنی و عملیاتی"""
    logging.info("🚀 ربات معامله‌گر در حال استارت...")
    database.init_db()
    
    while True:
        try:
            # ۱. پیش‌پردازش و آموزش
            train_model.train_ai_model()
            
            # ۲. بررسی بازار
            for pair in config.WATCHLIST:
                symbol = pair.split('/')[0]
                df = coinex_client.get_coinex_candles(pair)
                if df is None or df.empty: continue
                    
                df = indicators.calculate_indicators(df)
                signal = strategy.generate_signal(df, pair)
                
                if not signal: continue
                
                # ۳. تصمیم‌گیری هوشمند
                is_allowed, reason = check_ai_permission(signal)
                if not is_allowed:
                    logging.info(f"🚫 سیگنال {symbol} توسط هوش مصنوعی رد شد: {reason}")
                    continue
                
                # ۴. مدیریت ظرفیت و اجرا
                open_count = strategy.get_open_positions_count()
                if open_count < config.MAX_OPEN_POSITIONS:
                    database.save_signal_advanced(..., status="OPEN") # جزئیات کامل
                    telegram_bot.format_and_send_signal(signal)
                    coinex_client.open_position(signal)
                    logging.info(f"✅ پوزیشن {symbol} با موفقیت باز شد.")
                else:
                    database.save_signal_advanced(..., status="SKIPPED_CAPACITY")
                    telegram_bot.send_skipped_signal_message(signal, open_count)
                    logging.info(f"⚠️ ظرفیت تکمیل بود. سیگنال {symbol} ثبت شد ولی اجرا نشد.")

        except Exception as e:
            logging.error(f"❌ خطای بحرانی در حلقه اصلی: {e}")
            time.sleep(60) # در صورت خطا یک دقیقه صبر کن
            
        time.sleep(60) # فاصله زمانی استاندارد بین اسکن‌ها

if __name__ == "__main__":
    main_loop()

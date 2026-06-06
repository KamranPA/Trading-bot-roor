# main.py
# نسخه نهایی v7.3 - کامل، ایمن و مدیریت شده

import time
import logging
import config
from src import database, coinex_client, strategy, telegram_bot, indicators, train_model
from src.brain import check_ai_permission

# تنظیمات لاگ‌گذاری برای رهگیری خطاها در کنسول
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_bot():
    logging.info("🚀 استارت ربات هوشمند v7.3...")
    
    try:
        database.init_db()
    except Exception as e:
        logging.error(f"❌ خطای حیاتی در مقداردهی اولیه دیتابیس: {e}")
        return

    while True:
        try:
            # ۱. آموزش هوش مصنوعی (فقط اگر داده کافی باشد)
            train_model.train_ai_model()
            
            # ۲. اسکن بازار
            for pair in config.WATCHLIST:
                symbol = pair.split('/')[0]
                
                # دریافت داده با مدیریت خطا
                df = coinex_client.get_coinex_candles(pair)
                if df is None or df.empty:
                    continue
                    
                # محاسبات فنی
                df = indicators.calculate_indicators(df)
                
                # تولید سیگنال
                signal_result = strategy.generate_signal(df, pair)
                
                if signal_result and isinstance(signal_result, dict):
                    # اعتبارسنجی هوش مصنوعی
                    ai_approved, _ = check_ai_permission(signal_result)
                    if not ai_approved: continue 

                    # مدیریت ظرفیت پوزیشن‌ها
                    open_count = strategy.get_open_positions_count()
                    status = "OPEN" if open_count < config.MAX_OPEN_POSITIONS else "SKIPPED_CAPACITY"
                    
                    # ثبت در دیتابیس
                    database.save_signal_advanced(
                        symbol=symbol, direction=signal_result['direction'],
                        entry_price=signal_result['entry_price'], stop_loss=signal_result['stop_loss'],
                        tp1=signal_result['tp1'], tp2=signal_result['tp2'],
                        feat_adx=signal_result['feat_adx'], feat_vol_ratio=signal_result['feat_vol_ratio'],
                        feat_atr_percent=signal_result['feat_atr_percent'], feat_rsi=signal_result['feat_rsi'],
                        feat_trend_line=signal_result['feat_trend_line'], feat_ema_deviation=signal_result['feat_ema_deviation'],
                        feat_rsi_momentum=signal_result['feat_rsi_momentum'], feat_body_ratio=signal_result['feat_body_ratio'],
                        feat_high_volume_session=signal_result['feat_high_volume_session'], status=status
                    )

                    # ارسال به تلگرام و اجرای عملیات
                    if status == "SKIPPED_CAPACITY":
                        telegram_bot.send_skipped_signal_message(signal_result, open_count)
                    else:
                        telegram_bot.format_and_send_signal(signal_result)
                        coinex_client.open_position(signal_result)
            
            logging.info("✅ چرخه اسکن با موفقیت کامل شد. ۶۰ ثانیه استراحت...")
            time.sleep(60)

        except Exception as e:
            logging.error(f"⚠️ خطای غیرمنتظره در حلقه اصلی: {e}")
            time.sleep(30) # وقفه کوتاه در صورت بروز خطا قبل از تلاش مجدد

if __name__ == "__main__":
    run_bot()

# main.py
# نسخه نهایی v7.3 - مدیریت یکپارچه سیگنال‌های لایو و گزارش‌دهی هوشمند

import config
from src import database, coinex_client, strategy, telegram_bot, indicators, train_model

def run_bot():
    print("🤖 اسکنر هوشمند v7.3 در حال اجرای عملیات...")
    database.init_db()
    
    # آموزش مدل هوش مصنوعی قبل از شروع اسکن
    train_model.train_ai_model()
    
    for pair in config.WATCHLIST:
        symbol = pair.split('/')[0]
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty: continue
            
        df = indicators.calculate_indicators(df)
        signal_result = strategy.generate_signal(df, pair)
        
        if signal_result and isinstance(signal_result, dict):
            # ۱. بررسی فیلتر نرم (هوش مصنوعی)
            ai_approved, _ = check_ai_permission(signal_result)
            if not ai_approved:
                database.log_scan(symbol, "Blocked by AI")
                continue

            # ۲. بررسی ظرفیت و ثبت در دیتابیس
            open_count = strategy.get_open_positions_count()
            status = "OPEN" if open_count < config.MAX_OPEN_POSITIONS else "SKIPPED_CAPACITY"
            
            # ذخیره در دیتابیس (هم برای معاملات باز و هم فرصت‌های نادیده گرفته شده)
            database.save_signal_advanced(
                symbol=symbol, 
                direction=signal_result['direction'],
                entry_price=signal_result['entry_price'], 
                stop_loss=signal_result['stop_loss'],
                tp1=signal_result['tp1'], 
                tp2=signal_result['tp2'],
                feat_adx=signal_result['feat_adx'], 
                feat_vol_ratio=signal_result['feat_vol_ratio'],
                feat_atr_percent=signal_result['feat_atr_percent'], 
                feat_rsi=signal_result['feat_rsi'],
                feat_trend_line=signal_result['feat_trend_line'], 
                feat_ema_deviation=signal_result['feat_ema_deviation'],
                feat_rsi_momentum=signal_result['feat_rsi_momentum'], 
                feat_body_ratio=signal_result['feat_body_ratio'],
                feat_high_volume_session=signal_result['feat_high_volume_session'], 
                status=status
            )

            # ۳. ارسال گزارش به تلگرام بر اساس وضعیت
            if status == "SKIPPED_CAPACITY":
                # استفاده از تابع جدید برای گزارش فرصت‌های نادیده گرفته شده
                telegram_bot.send_skipped_signal_message(signal_result, open_count)
            else:
                # ارسال سیگنال عادی برای باز کردن پوزیشن
                telegram_bot.format_and_send_signal(signal_result)
                # در اینجا دستور باز کردن پوزیشن در صرافی را فراخوانی کنید
                # exchange.open_position(...)

if __name__ == "__main__":
    run_bot()

# main.py
# ... (ایمپورت‌ها)
from src import database, coinex_client, strategy, telegram_bot, indicators, train_model

def run_bot():
    print("🤖 اسکنر هوشمند v7.3 فعال شد...")
    database.init_db()
    
    # به‌روزرسانی پوزیشن‌های باز
    update_open_positions()
    
    for pair in config.WATCHLIST:
        symbol = pair.split('/')[0]
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty: continue
            
        df = indicators.calculate_indicators(df)
        signal_result = strategy.generate_signal(df, pair)
        
        if signal_result and isinstance(signal_result, dict):
            # فیلتر هوش مصنوعی
            ai_approved, _ = check_ai_permission(signal_result)
            if not ai_approved:
                database.log_scan(symbol, "Blocked by AI")
                continue

            # مدیریت ظرفیت
            open_count = strategy.get_open_positions_count()
            status = "OPEN" if open_count < config.MAX_OPEN_POSITIONS else "SKIPPED_CAPACITY"
            
            # ذخیره در دیتابیس (حتی اگر باز نشود)
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

            # گزارش‌دهی به تلگرام
            if status == "SKIPPED_CAPACITY":
                msg = (f"⚠️ **سیگنال نادیده گرفته شد (ظرفیت پر)**\n"
                       f"🪙 `{pair}` | {signal_result['direction']}\n"
                       f"📊 پوزیشن‌های باز: {open_count}/{config.MAX_OPEN_POSITIONS}\n"
                       f"💡 جهت بررسی مدل هوش مصنوعی ثبت شد.")
                telegram_bot.send_telegram_message(msg)
            else:
                telegram_bot.format_and_send_signal(signal_result)

if __name__ == "__main__":
    run_bot()

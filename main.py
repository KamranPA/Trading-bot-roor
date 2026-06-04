        if signal_result and isinstance(signal_result, dict):
            direction = signal_result['direction']
            print(f"🎯 استراتژی روی {symbol} سیگنال {direction} صادر کرد.")
            
            # ارسال ویژگی‌های یادگیری ماشین استخراج شده به دیتابیس مرکزی جهت ذخیره‌سازی ابدی
            database.save_signal_advanced(
                symbol=symbol,
                direction=direction,
                entry_price=signal_result['entry_price'],
                stop_loss=signal_result['stop_loss'],
                tp1=signal_result['tp1'],
                tp2=signal_result['tp2'],
                feat_adx=signal_result['feat_adx'],
                feat_vol_ratio=signal_result['feat_vol_ratio'],
                feat_atr_percent=signal_result['feat_atr_percent'],
                status="OPEN"
            )
            
            # فیلتر ۸ ساعته تلگرام
            if is_telegram_locked_8h(symbol, hours_limit=8):
                print(f"⏭️ ارسال به تلگرام مسدود شد: فیلتر ۸ ساعته برای {symbol} فعال است.")
                continue
                
            telegram_bot.format_and_send_signal(signal_result)

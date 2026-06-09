# FILE PATH: /main.py
# ... (سایر ایمپورت‌ها بدون تغییر)

def run_bot():
    logging.info("🤖 اسکنر هوشمند v7.2 فعال شد.")
    database.init_db()
    
    # اصلاح فراخوانی تابع برای جلوگیری از خطای Argument
    try:
        positions = database.manage_open_positions()
        logging.info(f"پوزیشن‌های باز جاری: {len(positions)}")
    except Exception as e:
        logging.error(f"خطا در مدیریت پوزیشن‌ها: {e}")
    
    # اسکن بازار
    watchlist = getattr(config, 'WATCHLIST', [])
    for pair in watchlist:
        try:
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty: continue
                
            df = indicators.calculate_indicators(df)
            signal_result = strategy.generate_signal(df, pair)
            
            if signal_result:
                # استفاده از تابع اصلاح شده در database.py
                database.save_signal_advanced(
                    symbol=pair, 
                    direction=signal_result.get('direction'),
                    entry_price=signal_result.get('entry_price'),
                    stop_loss=signal_result.get('stop_loss'),
                    tp1=signal_result.get('tp1'),
                    tp2=signal_result.get('tp2')
                )
                telegram_bot.format_and_send_signal(signal_result)
                logging.info(f"✅ سیگنال برای {pair} ارسال شد و در دیتابیس ذخیره گردید.")
        
        except Exception as e:
            logging.error(f"خطا در پردازش {pair}: {e}")
            time.sleep(1)

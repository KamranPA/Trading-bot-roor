# ---------------------------------------------------------
# FILE PATH: main.py (نسخه نهایی یکپارچه با Machine Learning و Supabase)
# ---------------------------------------------------------
import os
import sys
import logging
import threading
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# اضافه کردن مسیر پروژه به سیستم
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    import config
    from src import database, coinex_client, strategy, telegram_bot, indicators, optimizer
    from src.brain import TradingBrain
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BRAIN = TradingBrain()
db_lock = threading.Lock()

def check_exits():
    """بررسی قیمت و بستن پوزیشن‌ها در دیتابیس ابری"""
    try:
        positions = database.get_open_positions() 
        for pos in positions:
            sig_id = pos['id']
            symbol = pos['symbol']
            direction = pos['direction']
            entry = pos['entry_price']
            sl = pos['stop_loss']
            tp2 = pos['tp2']
            
            df = coinex_client.get_coinex_candles(symbol, limit=1)
            if df is None or df.empty: continue
            current_price = float(df.iloc[-1]['Close'])
            
            pnl = 0.0
            should_close = False
            
            # محاسبه PNL با در نظر گرفتن برخورد به تارگت یا حد ضرر
            if direction == "LONG":
                if current_price <= sl: 
                    pnl = ((sl - entry) / entry) * 100
                    should_close = True
                elif current_price >= tp2: 
                    pnl = ((tp2 - entry) / entry) * 100
                    should_close = True
            elif direction == "SHORT":
                if current_price >= sl: 
                    pnl = ((entry - sl) / entry) * 100
                    should_close = True
                elif current_price <= tp2: 
                    pnl = ((entry - tp2) / entry) * 100
                    should_close = True
            
            if should_close:
                # ثبت دقیق PNL برای آموزش‌های ماهانه ماشین لرنینگ
                database.update_position_status(sig_id, 'CLOSED', pnl)
                logging.info(f"✅ پوزیشن {symbol} بسته شد. سود/ضرر: {pnl:.2f}%")
    except Exception as e:
        logging.error(f"⚠️ خطا در بررسی پوزیشن‌های باز ابری: {e}")

def heartbeat_job():
    try:
        watchlist_count = len(getattr(config, 'WATCHLIST', []))
        models_dir = os.path.join(BASE_DIR, "src", "models")
        model_count = len([f for f in os.listdir(models_dir) if f.endswith('.pkl')]) if os.path.exists(models_dir) else 0
        telegram_bot.send_heartbeat_report(watchlist_count, model_count)
        logging.info("✅ گزارش Heartbeat با موفقیت ارسال شد.")
    except Exception as e:
        logging.error(f"⚠️ خطا در ارسال گزارش Heartbeat: {e}")

def process_pair(pair):
    """پردازش مستقل هر جفت‌ارز در ترد جداگانه"""
    try:
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty: return pair, False
        
        df = indicators.calculate_indicators(df)
        res = strategy.generate_signal(df, pair, model=BRAIN)
        signal = res if isinstance(res, dict) else None
        
        t_score = res.get('total_score', 0.0) if isinstance(res, dict) else 0.0
        ai_s = res.get('ai_score', 0.0) if isinstance(res, dict) else 0.0
        rsi_s = res.get('rsi_score', 0.0) if isinstance(res, dict) else 0.0
        adx_s = res.get('adx_score', 0.0) if isinstance(res, dict) else 0.0
        ema_s = res.get('ema_score', 0.0) if isinstance(res, dict) else 0.0

        with db_lock:
            if signal and signal.get('direction') is not None:
                tele_signal = signal.copy()
                tele_signal['pair_display'] = "MATIC/USDT (POL)" if pair == "POL/USDT" else pair

                # آماده‌سازی دیکشنری برای ثبت در دیتابیس (حذف کلیدهای غیرمرتبط با دیتابیس)
                signal.pop('pair', None) 
                signal.pop('symbol', None)
                for k in ['total_score', 'ai_score', 'rsi_score', 'adx_score', 'ema_score']:
                    signal.pop(k, None)

                # **signal اکنون حاوی تمام سنسورهای ML و position_size است
                database.save_signal_advanced(pair=pair, **signal)
                database.log_scan_status(pair, "SIGNAL SENT", total=t_score, ai=ai_s, rsi=rsi_s, adx=adx_s, ema=ema_s)
                
                try:
                    telegram_bot.format_and_send_signal(tele_signal)
                    logging.info(f"🚀 سیگنال {pair} با موفقیت به تلگرام مخابره شد.")
                except Exception as t_err:
                    logging.error(f"⚠️ خطا در ارسال تلگرام برای {pair}: {t_err}")
            else:
                database.log_scan_status(pair, "nosignal", total=t_score, ai=ai_s, rsi=rsi_s, adx=adx_s, ema=ema_s)
                
        return pair, True
    except Exception as e:
        logging.error(f"❌ خطا در پردازش {pair}: {e}")
        return pair, False

def run_auto_optimization():
    try:
        # توجه: این تابع در حال حاضر تعداد پوزیشن‌های "باز" را می‌شمارد. 
        # اگر می‌خواهید پس از هر ۵۰ معامله بسته شده مدل بهینه شود، باید کوئری دیتابیس تغییر کند.
        count = database.get_open_positions_count()
        if count > 0 and count % 50 == 0:
            logging.info("⚙️ سیستم به حد نصاب رسید: اجرای پروسه ارتقای خودکار...")
            optimizer.optimize_all(mode="live")
    except Exception as e:
        logging.error(f"⚠️ خطا در پروسه خودارتقایی: {e}")

def run_bot():
    logging.info("🤖 اسکنر هوشمند فعال شد.")
    database.init_db() # دیتابیس ابری را آماده می‌کند
    
    check_exits()
    run_auto_optimization()
    
    watchlist = getattr(config, 'WATCHLIST', [])
    
    # استفاده از as_completed برای مدیریت بهتر تردها و جلوگیری از زامبی شدن پردازش‌ها
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(process_pair, pair): pair for pair in watchlist}
        for future in as_completed(futures):
            try:
                future.result() # خطاها در صورت وجود اینجا مچ‌گیری می‌شوند
            except Exception as exc:
                pair = futures[future]
                logging.error(f"⚠️ اجرای ترد برای {pair} با خطای غیرمنتظره متوقف شد: {exc}")

if __name__ == "__main__":
    # اگر اسکریپت با Cron Job به صورت مداوم اجرا می‌شود، این شرط فقط یک بار در ساعت 22 (UTC) عمل می‌کند
    if datetime.datetime.utcnow().hour == 22 and datetime.datetime.utcnow().minute < 10:
        heartbeat_job()
    run_bot()

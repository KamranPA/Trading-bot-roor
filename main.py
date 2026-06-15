# ---------------------------------------------------------
# FILE PATH: main.py (اصلاح شده: مدیریت امن پوزیشن‌ها و یکپارچه‌سازی متغیرها)
# ---------------------------------------------------------
import os
import sys
import logging
import sqlite3
import threading
import datetime
from concurrent.futures import ThreadPoolExecutor

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
    """
    تابع بررسی قیمت و بستن پوزیشن‌ها در صورت رسیدن به حد سود یا ضرر.
    اصلاح شده جهت هماهنگی کامل با حروف کوچک ستون‌ها و استخراج ایمن داده‌های دیتابیس.
    """
    try:
        # دریافت پوزیشن‌های باز از دیتابیس
        positions = database.get_open_positions() 
        if not positions:
            return

        for pos in positions:
            try:
                # استخراج ایمن داده‌ها بر اساس طول آرایه پوزیشن جهت جلوگیری از خطای Unpacking
                sig_id = pos[0]
                symbol = pos[1] if len(pos) > 1 else None
                
                # تطبیق داینامیک بر اساس ساختار استاندارد دیتابیس شما:
                # (id, symbol, direction, entry_price, stop_loss, tp1, tp2, status, ...)
                if isinstance(symbol, str) and (symbol.endswith('USDT') or 'USDT' in symbol):
                    direction = pos[2]
                    entry = float(pos[3])
                    sl = float(pos[4])
                    tp1 = float(pos[5])
                    tp2 = float(pos[6])
                else:
                    # اگر فیلد دوم چیز دیگری بود (مانند زمان یا کدهای کاستوم)، فرمت ثانویه را ست می‌کند
                    symbol = pos[2]
                    direction = pos[3]
                    entry = float(pos[4])
                    sl = float(pos[5])
                    tp1 = float(pos[6])
                    tp2 = float(pos[7])

                # فراخوانی ایمن تابع دریافت کندل‌ها از ماژول صرافی
                if hasattr(coinex_client, 'get_coinex_candles'):
                    df = coinex_client.get_coinex_candles(symbol, limit=5)
                else:
                    df = coinex_client.get_candles(symbol, limit=5)

                if df is None or df.empty: 
                    continue
                
                # اصلاح کلیدی: استفاده از حروف کوچک 'close' برای تطابق با ساختار صرافی و سیستم اندیکاتورها
                if 'close' in df.columns:
                    current_price = float(df.iloc[-1]['close'])
                elif 'Close' in df.columns:
                    current_price = float(df.iloc[-1]['Close'])
                else:
                    current_price = float(df.iloc[-1].iloc[4]) # به عنوان جایگزین ایندکس مپ قیمتی

                # منطق خروج هوشمند و محاسبه PnL
                pnl = 0.0
                should_close = False
                
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
                    database.update_position_status(sig_id, 'CLOSED', pnl)
                    logging.info(f"✅ پوزیشن {symbol} بسته شد. سود/ضرر: {pnl:.2f}%")
                    
                    # اطلاع‌رسانی خروج به تلگرام
                    try:
                        telegram_bot.send_message(f"🚨 **خروج از پوزیشن {symbol}**\nجهت: {direction}\nسود/ضرر نهایی: {pnl:.2f}%")
                    except Exception:
                        pass
            except Exception as pos_err:
                logging.error(f"خطا در پردازش پوزیشن منفرد {pos}: {pos_err}")
                continue

    except Exception as e:
        logging.error(f"خطا در بررسی پوزیشن‌های باز: {e}")

def heartbeat_job():
    """
    ارسال گزارش وضعیت ربات به تلگرام در ساعت مشخص شده
    """
    try:
        watchlist_count = len(getattr(config, 'WATCHLIST', []))
        models_dir = os.path.join(BASE_DIR, "src", "models")
        model_count = len([f for f in os.listdir(models_dir) if f.endswith('.pkl')]) if os.path.exists(models_dir) else 0
        telegram_bot.send_heartbeat_report(watchlist_count, model_count)
        logging.info("✅ گزارش Heartbeat با موفقیت ارسال شد.")
    except Exception as e:
        logging.error(f"خطا در ارسال گزارش Heartbeat: {e}")

def process_pair(pair):
    """
    پردازش موازی هر جفت ارز: دریافت داده، اندیکاتورها، بررسی استراتژی و صدور سیگنال
    """
    try:
        if hasattr(coinex_client, 'get_coinex_candles'):
            df = coinex_client.get_coinex_candles(pair)
        else:
            df = coinex_client.get_candles(pair)

        if df is None or df.empty: 
            return
            
        df = indicators.calculate_indicators(df)
        signal = strategy.generate_signal(df, pair, model=BRAIN)
        
        with db_lock:
            if signal:
                database.save_signal_advanced(pair=pair, **signal)
                database.log_scan_status(pair, "SIGNAL SENT")
                telegram_bot.format_and_send_signal(signal)
            else:
                database.log_scan_status(pair, "nosignal")
    except Exception as e:
        logging.error(f"خطا در پردازش {pair}: {e}")

def run_auto_optimization():
    """
    بررسی خودکار تعداد سیگنال‌ها جهت ارتقا و بهینه‌سازی دوره ای پارامترها
    """
    db_path = database.DB_PATH 
    try:
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT count(*) FROM signals").fetchone()[0]
            if count > 0 and count % 50 == 0:
                logging.info("⚙️ سیستم به حد نصاب رسید: اجرای پروسه ارتقای خودکار...")
                optimizer.optimize_all(mode="live")
    except Exception as e:
        logging.error(f"خطا در پروسه خودارتقایی: {e}")

def run_bot():
    """
    راه اندازی و مدیریت چرخه اجرایی اسکنر
    """
    logging.info("🤖 اسکنر هوشمند v8.2 (پشتیبانی موازی ۱۱ ارز) فعال شد.")
    database.init_db()
    
    # پایشگر هوشمند خروج پوزیشن‌ها قبل از اسکن جدید رونمایی می‌شود
    check_exits()                      
    
    # اجرای بهینه‌سازی در صورت نیاز
    run_auto_optimization()
    
    # اسکن موازی واچ‌لیست با استفاده از تردها
    watchlist = getattr(config, 'WATCHLIST', [])
    with ThreadPoolExecutor(max_workers=12) as executor:
        executor.map(process_pair, watchlist)

if __name__ == "__main__":
    current_hour = datetime.datetime.utcnow().hour
    if current_hour == 22:
        heartbeat_job()
    run_bot()

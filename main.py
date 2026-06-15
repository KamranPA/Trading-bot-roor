# ---------------------------------------------------------
# FILE PATH: main.py (نسخه نهایی و کامل - رفع مشکل گیت‌هاب اکشنز و ثبت امتیاز لایو)
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
    بررسی قیمت لحظه‌ای بازار و بستن پوزیشن‌های باز در صورت رسیدن به حد سود یا ضرر.
    """
    try:
        positions = database.get_open_positions() 
        for pos in positions:
            sig_id, _, symbol, direction, entry, sl, tp1, tp2, status, _, _, *_ = pos
            
            df = coinex_client.get_coinex_candles(symbol, limit=1)
            if df is None or df.empty: continue
            current_price = df.iloc[-1]['Close']
            
            pnl = 0
            should_close = False
            if direction == "LONG":
                if current_price <= sl: pnl = ((sl - entry) / entry) * 100; should_close = True
                elif current_price >= tp2: pnl = ((tp2 - entry) / entry) * 100; should_close = True
            elif direction == "SHORT":
                if current_price >= sl: pnl = ((entry - sl) / entry) * 100; should_close = True
                elif current_price <= tp2: pnl = ((entry - tp2) / entry) * 100; should_close = True
            
            if should_close:
                database.update_position_status(sig_id, 'CLOSED', pnl)
                logging.info(f"✅ پوزیشن {symbol} بسته شد. سود/ضرر: {pnl:.2f}%")
    except Exception as e:
        logging.error(f"خطا در بررسی پوزیشن‌های باز: {e}")

def heartbeat_job():
    """ارسال گزارش وضعیت سلامت ربات"""
    try:
        watchlist_count = len(getattr(config, 'WATCHLIST', []))
        models_dir = os.path.join(BASE_DIR, "src", "models")
        model_count = len([f for f in os.listdir(models_dir) if f.endswith('.pkl')]) if os.path.exists(models_dir) else 0
        telegram_bot.send_heartbeat_report(watchlist_count, model_count)
        logging.info("✅ گزارش Heartbeat با موفقیت ارسال شد.")
    except Exception as e:
        logging.error(f"خطا در ارسال گزارش Heartbeat: {e}")

def process_pair(pair):
    """پردازش جفت‌ارز و ثبت دقیق وضعیت در دیتابیس"""
    try:
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty: return
        df = indicators.calculate_indicators(df)
        
        signal = strategy.generate_signal(df, pair, model=BRAIN)
        
        # استخراج امتیاز به صورت ایمن
        current_score = 0.0
        if isinstance(signal, dict):
            current_score = float(signal.get('signal_score', 0.0))
        elif 'feat_rsi' in df.columns: # مثال: اگر سیگنال نبود امتیاز تقریبی از RSI بردار
            current_score = 0.0
            
        with db_lock:
            if signal and isinstance(signal, dict):
                database.save_signal_advanced(pair=pair, **signal)
                # ارسال ۳ آرگومان الزامی: (ارز، وضعیت، امتیاز)
                database.log_scan_status(pair, "SIGNAL SENT", current_score)
                telegram_bot.format_and_send_signal(signal)
            else:
                # ارسال ۳ آرگومان الزامی: (ارز، وضعیت، امتیاز)
                database.log_scan_status(pair, "nosignal", current_score)
                
    except Exception as e:
        logging.error(f"خطا در پردازش {pair}: {e}")
        try:
            with db_lock:
                # ثبت خطا با امتیاز صفر
                database.log_scan_status(pair, "ERROR_OCCURRED", 0.0)
        except:
            pass

def run_auto_optimization():
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
    logging.info("🤖 اسکنر هوشمند v8.5 (ثبت همزمان لاگ و امتیاز لایو) فعال شد.")
    database.init_db()
    
    check_exits()                      
    run_auto_optimization()
    
    watchlist = getattr(config, 'WATCHLIST', [])
    logging.info(f"📋 تعداد ارزهای واچ‌لیست جهت اسکن: {len(watchlist)} ارز")
    
    if not watchlist:
        logging.warning("⚠️ واچ‌لیست خالی است!")
        return

    with ThreadPoolExecutor(max_workers=12) as executor:
        list(executor.map(process_pair, watchlist))
        
    logging.info("🏁 چرخه اسکن تمام واچ‌لیست به پایان رسید و داده‌ها ذخیره شدند.")

if __name__ == "__main__":
    current_hour = datetime.datetime.utcnow().hour
    if current_hour == 22:
        heartbeat_job()
    run_bot()

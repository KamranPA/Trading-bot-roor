# ---------------------------------------------------------
# FILE PATH: main.py (نسخه اصلاح شده با سیستم ثبت امتیازات)
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
    """بررسی قیمت و بستن پوزیشن‌ها در صورت رسیدن به حد سود یا ضرر"""
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
    try:
        watchlist_count = len(getattr(config, 'WATCHLIST', []))
        models_dir = os.path.join(BASE_DIR, "src", "models")
        model_count = len([f for f in os.listdir(models_dir) if f.endswith('.pkl')]) if os.path.exists(models_dir) else 0
        telegram_bot.send_heartbeat_report(watchlist_count, model_count)
        logging.info("✅ گزارش Heartbeat با موفقیت ارسال شد.")
    except Exception as e:
        logging.error(f"خطا در ارسال گزارش Heartbeat: {e}")

def process_pair(pair):
    try:
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty: return
        df = indicators.calculate_indicators(df)
        
        # فرض می‌کنیم تابع استراتژی شما اصلاح شده و علاوه بر سیگنال، امتیازات را هم برمی‌گرداند.
        # برای جلوگیری از خطا، استراتژی باید یک دیکشنری حاوی اطلاعات امتیاز یا خود سیگنال برگرداند.
        res = strategy.generate_signal(df, pair, model=BRAIN)
        
        # استخراج اطلاعات امتیازدهی در صورت وجود در خروجی استراتژی
        # اگر استراتژی شما فقط خودِ دیکشنری سیگنال را می‌دهد، امتیازها را از درون آن یا به صورت پیش‌فرض استخراج می‌کنیم
        signal = res if isinstance(res, dict) else None
        
        # مقادیر پیش‌فرض امتیاز برای ثبت در scan_logs در صورتی که در خروجی استراتژی فیلد مجزا ندارند
        t_score = res.get('total_score', 0.0) if isinstance(res, dict) else 0.0
        ai_s = res.get('ai_score', 0.0) if isinstance(res, dict) else 0.0
        rsi_s = res.get('rsi_score', 0.0) if isinstance(res, dict) else 0.0
        adx_s = res.get('adx_score', 0.0) if isinstance(res, dict) else 0.0
        ema_s = res.get('ema_score', 0.0) if isinstance(res, dict) else 0.0

        with db_lock:
            if signal and signal.get('direction') is not None:
                # حذف کلیدهای اضافی برای جلوگیری از خطای multiple values
                signal.pop('pair', None) 
                signal.pop('symbol', None)
                
                # پاکسازی کلیدهای مربوط به امتیاز قبل از ذخیره در جدول اصلی سیگنال‌ها (اگر وجود دارند)
                for k in ['total_score', 'ai_score', 'rsi_score', 'adx_score', 'ema_score']:
                    signal.pop(k, None)

                database.save_signal_advanced(pair=pair, **signal)
                database.log_scan_status(pair, "SIGNAL SENT", total=t_score, ai=ai_s, rsi=rsi_s, adx=adx_s, ema=ema_s)
                telegram_bot.format_and_send_signal(signal)
            else:
                database.log_scan_status(pair, "nosignal", total=t_score, ai=ai_s, rsi=rsi_s, adx=adx_s, ema=ema_s)
    except Exception as e:
        logging.error(f"خطا در پردازش {pair}: {e}")

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
    logging.info("🤖 اسکنر هوشمند فعال شد.")
    database.init_db()
    
    check_exits()
    run_auto_optimization()
    
    watchlist = getattr(config, 'WATCHLIST', [])
    with ThreadPoolExecutor(max_workers=12) as executor:
        executor.map(process_pair, watchlist)

if __name__ == "__main__":
    if datetime.datetime.utcnow().hour == 22:
        heartbeat_job()
    run_bot()

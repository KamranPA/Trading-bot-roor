# ---------------------------------------------------------
# FILE PATH: main.py (نسخه نهایی سازگار با Supabase PostgreSQL + Dynamic Params)
# ---------------------------------------------------------
import os
import sys
import logging
import threading
import datetime
import json
from concurrent.futures import ThreadPoolExecutor

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

def get_symbol_params(symbol):
    """
    خواندن پارامترهای اختصاصی هر ارز از فایل best_params.json برای محیط لایو.
    در صورتی که پارامتری یافت نشود، از مقادیر پیش‌فرض config استفاده می‌شود.
    """
    params_file = os.path.join(BASE_DIR, 'best_params.json')
    
    # مقادیر پیش‌فرض (در صورت نبودن تنظیمات اختصاصی)
    default_params = {
        'ADX_THRESHOLD': config.ADX_THRESHOLD if hasattr(config, 'ADX_THRESHOLD') else 15.0,
        'SWING_WINDOW': config.SWING_WINDOW if hasattr(config, 'SWING_WINDOW') else 3,
        'SL_RATIO': config.SL_RATIO if hasattr(config, 'SL_RATIO') else 1.0,
        'TP_RATIO': config.TP_RATIO if hasattr(config, 'TP_RATIO') else 1.5,
        'RSI_MIDLINE': 50.0
    }
    
    if os.path.exists(params_file):
        try:
            with open(params_file, 'r') as f:
                all_params = json.load(f)
                if symbol in all_params:
                    # ترکیب تنظیمات اختصاصی با پیش‌فرض‌ها
                    return {**default_params, **all_params[symbol]}
        except Exception as e:
            logging.error(f"⚠️ خطا در خواندن فایل best_params.json برای ارز {symbol}: {e}")
            
    return default_params

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
        logging.error(f"خطا در بررسی پوزیشن‌های باز ابری: {e}")

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
        
        # ۱. دریافت پارامترهای اختصاصی همین ارز
        sym_params = get_symbol_params(pair)
        
        # ۲. ارسال پارامترها به ماژول استراتژی برای تصمیم‌گیری
        res = strategy.generate_signal(df, pair, model=BRAIN, params=sym_params)
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

                signal.pop('pair', None) 
                signal.pop('symbol', None)
                for k in ['total_score', 'ai_score', 'rsi_score', 'adx_score', 'ema_score']:
                    signal.pop(k, None)

                database.save_signal_advanced(pair=pair, **signal)
                database.log_scan_status(pair, "SIGNAL SENT", total=t_score, ai=ai_s, rsi=rsi_s, adx=adx_s, ema=ema_s)
                
                try:
                    telegram_bot.format_and_send_signal(tele_signal)
                    logging.info(f"🚀 سیگنال {pair} با موفقیت به تلگرام مخابره شد.")
                except Exception as t_err:
                    logging.error(f"⚠️ خطا در ارسال تلگرام برای {pair}: {t_err}")
            else:
                database.log_scan_status(pair, "nosignal", total=t_score, ai=ai_s, rsi=rsi_s, adx=adx_s, ema=ema_s)
    except Exception as e:
        logging.error(f"خطا در پردازش {pair}: {e}")

def run_auto_optimization():
    try:
        count = database.get_open_positions_count()
        if count % 50 == 0 and count > 0:
            logging.info("⚙️ سیستم به حد نصاب رسید: اجرای پروسه ارتقای خودکار...")
            optimizer.optimize_all(mode="live")
    except Exception as e:
        logging.error(f"خطا در پروسه خودارتقایی: {e}")

def run_bot():
    logging.info("🤖 اسکنر هوشمند فعال شد.")
    database.init_db() # دیتابیس ابری را آماده می‌کند
    
    check_exits()
    run_auto_optimization()
    
    watchlist = getattr(config, 'WATCHLIST', [])
    with ThreadPoolExecutor(max_workers=12) as executor:
        executor.map(process_pair, watchlist)

if __name__ == "__main__":
    if datetime.datetime.utcnow().hour == 22:
        heartbeat_job()
    run_bot()

# ---------------------------------------------------------
# FILE NAME: main.py
# FILE PATH: /main.py
# ---------------------------------------------------------
import os
import sys
import logging
import time
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, 'src')

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    import config
    from src import database, coinex_client, strategy, telegram_bot, strategy_utils, optimizer, brain
except ImportError as e:
    logging.critical(f"❌ خطای بحرانی در لود ماژول‌ها: {e}")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def run_auto_optimization():
    try:
        db_path = getattr(database, 'DB_NAME', os.path.join(BASE_DIR, 'data', 'trading_bot.db'))
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT count(*) FROM signals WHERE status = 'CLOSED'").fetchone()[0]
            if count > 0 and count % 50 == 0:
                logging.info(f"🚀 شروع ارتقای هوشمند پارامترها در معامله {count}...")
                optimizer.optimize()
    except Exception as e:
        logging.error(f"⚠️ خطا در پروسه خودارتقایی: {e}")

def run_bot():
    logging.info("🤖 اسکنر هوشمند v7.2 فعال شد.")
    database.init_db()
    
    try:
        database.manage_open_positions()
    except Exception as e:
        logging.error(f"⚠️ خطا در مدیریت پوزیشن‌ها: {e}")
    
    run_auto_optimization()
    trading_brain = brain.TradingBrain()
    
    watchlist = getattr(config, 'WATCHLIST', [])
    logging.info(f"🔍 شروع اسکن {len(watchlist)} جفت ارز در تایم‌فریم {config.TIMEFRAME}...")
    
    for pair in watchlist:
        try:
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty:
                continue
                
            # محاسبه شاخص‌های قیمتی جدید بدون حجم
            df = strategy_utils.calculate_indicators(df)
            
            # بررسی شرایط استراتژی شکست سقف و کف قیمت
            signal_result = strategy.generate_signal(df, pair)
            
            if signal_result:
                ai_features = {k: v for k, v in signal_result.items() if k.startswith('feat_')}
                is_approved_by_ai = trading_brain.predict(ai_features)
                
                if is_approved_by_ai:
                    pop_keys = ['pair', 'position_size']
                    db_features = {k: v for k, v in signal_result.items() if k not in pop_keys}
                    
                    database.save_signal_advanced(
                        symbol=pair,
                        direction=signal_result['direction'],
                        entry_price=signal_result['entry_price'],
                        stop_loss=signal_result['stop_loss'],
                        tp1=signal_result['tp1'],
                        tp2=signal_result['tp2'],
                        **ai_features
                    )
                    
                    telegram_bot.format_and_send_signal(signal_result)
                    logging.info(f"✅ سیگنال برای {pair} صادر و به تلگرام ارسال شد.")
                else:
                    logging.info(f"🧠 [هوش مصنوعی]: سیگنال {pair} به دلیل ریسک بالا رد شد.")
        
        except Exception as e:
            logging.error(f"❌ خطا در پردازش جفت ارز {pair}: {e}")
            time.sleep(1)
            
    logging.info("🏁 اسکن دوره‌ای با موفقیت پایان یافت. سیستم در انتظار چرخه بعدی...")

if __name__ == "__main__":
    run_bot()

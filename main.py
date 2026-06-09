# ---------------------------------------------------------
# FILE NAME: main.py
# FILE PATH: /main.py
# ---------------------------------------------------------

import os
import sys
import logging
import time
import sqlite3

# ۱. تنظیم هوشمند مسیرها (بدون وابستگی به محل اجرا در گیت‌هاب)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE_DIR, 'src')

# افزودن مسیرها به ابتدای لیست جستجوی پایتون برای اولویت بالا
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# ۲. واردات ماژول‌ها با مدیریت خطا برای دیباگ سریع‌تر
try:
    import config
    from src import database, coinex_client, strategy, telegram_bot, strategy_utils, optimizer, brain
except ImportError as e:
    logging.critical(f"❌ خطای بحرانی در وارد کردن ماژول‌ها: {e}")
    sys.exit(1)

# ۳. تنظیم لاگ‌گیری استاندارد برای گیت‌هاب اکشنز
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def run_auto_optimization():
    """📊 فراخوانی بهینه‌ساز پس از رسیدن معاملات بسته شده به ضریب ۵۰"""
    try:
        db_path = getattr(database, 'DB_NAME', os.path.join(BASE_DIR, 'data', 'trading_bot.db'))
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                count = conn.execute("SELECT count(*) FROM signals WHERE status = 'CLOSED'").fetchone()[0]
            
            if count > 0 and count % 50 == 0:
                logging.info(f"🚀 رسیدن به {count} معامله بسته شده؛ شروع ارتقای هوشمند پارامترها...")
                optimizer.optimize()
    except Exception as e:
        logging.error(f"⚠️ خطا در پروسه خودارتقایی دیتابیس: {e}")

def run_bot():
    logging.info("🤖 اسکنر هوشمند v7.2 فعال شد.")
    
    # راه‌اندازی و پایش پایگاه داده
    database.init_db()
    
    try:
        database.manage_open_positions()
    except Exception as e:
        logging.error(f"⚠️ خطا در مدیریت پوزیشن‌های باز: {e}")
    
    # بررسی نیاز به بهینه‌سازی پارامترها
    run_auto_optimization()
    
    # مقداردهی اولیه به مغز متفکر هوش مصنوعی
    trading_brain = brain.TradingBrain()
    
    # شروع اسکن چرخشی واچ‌لیست بهینه‌سازی شده
    watchlist = getattr(config, 'WATCHLIST', [])
    logging.info(f"🔍 شروع اسکن {len(watchlist)} جفت ارز در تایم‌فریم {config.TIMEFRAME}...")
    
    for pair in watchlist:
        try:
            # ۱. دریافت داده‌های کندل استیک از صرافی کوین‌اکس
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty:
                logging.warning(f"⚠️ دیتایی برای {pair} دریافت نشد. رفتن به ارز بعدی...")
                continue
                
            # ۲. محاسبه دقیق ۹ فیلتر قیمتی و مومنتوم
            df = strategy_utils.calculate_indicators(df)
            
            # ۳. بررسی شرایط شکست (Breakout) قله یا دره اخیر
            signal_result = strategy.generate_signal(df, pair)
            
            if signal_result:
                # ۴. فیلترینگ نهایی سیگنال توسط مدل یادگیری ماشین (AI Filter)
                ai_features = {k: v for k, v in signal_result.items() if k.startswith('feat_')}
                is_approved_by_ai = trading_brain.predict(ai_features)
                
                if is_approved_by_ai:
                    # حذف کلیدهای موقتی قبل از ذخیره در دیتابیس
                    pop_keys = ['pair', 'position_size']
                    db_features = {k: v for k, v in signal_result.items() if k not in pop_keys}
                    
                    # ۵. ذخیره سیگنال تایید شده در SQLite
                    database.save_signal_advanced(
                        symbol=pair,
                        direction=signal_result['direction'],
                        entry_price=signal_result['entry_price'],
                        stop_loss=signal_result['stop_loss'],
                        tp1=signal_result['tp1'],
                        tp2=signal_result['tp2'],
                        **{k: v for k, v in ai_features.items()}
                    )
                    
                    # ۶. ارسال سیگنال به کانال یا گروه تلگرام شما
                    telegram_bot.format_and_send_signal(signal_result)
                    logging.info(f"✅ سیگنال خرید/فروش برای {pair} با موفقیت صادر و ارسال شد.")
                else:
                    logging.info(f"🧠 [هوش مصنوعی]: سیگنال {pair} به دلیل ریسک بالا رد شد.")
        
        except Exception as e:
            logging.error(f"❌ خطا در پردازش چرخشی جفت ارز {pair}: {e}")
            time.sleep(1)
            
    logging.info("🏁 اسکن دوره‌ای با موفقیت پایان یافت. سیستم در انتظار چرخه بعدی...")

if __name__ == "__main__":
    run_bot()

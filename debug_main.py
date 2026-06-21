#!/usr/bin/env python3
# debug_main.py - شبیه‌سازی ذخیره سیگنال برای دیباگ

import os
import sys
import logging
import random
from datetime import datetime

# تنظیم لاگ
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# اضافه کردن مسیر src
sys.path.insert(0, 'src')

from database import init_db, save_signal_advanced, get_open_positions_count

def simulate_signal_save(pair="BTC-USD"):
    """شبیه‌سازی ذخیره یک سیگنال"""
    logger.info(f"🔍 شبیه‌سازی ذخیره سیگنال برای {pair}")
    
    # داده‌های تست (مشابه چیزی که main.py تولید می‌کند)
    signal_data = {
        'direction': 'LONG' if random.random() > 0.5 else 'SHORT',
        'entry_price': 30000 + random.randint(-1000, 1000),
        'stop_loss': 29000 + random.randint(-500, 500),
        'tp1': 31000 + random.randint(-500, 500),
        'tp2': 32000 + random.randint(-500, 500),
        'swing_ref': 29500 + random.randint(-200, 200),
        'total_score': 65 + random.randint(0, 30),
        'ai_score': 60 + random.randint(0, 35),
        'rsi_score': 50 + random.randint(0, 40),
        'adx_score': 50 + random.randint(0, 40),
        'ema_score': 50 + random.randint(0, 40),
        'feat_adx': 20 + random.randint(0, 30),
        'feat_rsi': 40 + random.randint(0, 40),
        'feat_rsi_momentum': round(random.uniform(-5, 5), 2),
        'feat_ema_deviation': round(random.uniform(-3, 3), 2),
        'feat_atr_percent': round(random.uniform(0.1, 2.0), 2),
        'feat_trend_line': round(random.uniform(-2, 2), 2),
        'feat_body_ratio': round(random.uniform(0.1, 1.5), 2)
    }
    
    logger.info(f"📊 داده‌های سیگنال: {signal_data}")
    
    try:
        signal_id = save_signal_advanced(pair, **signal_data)
        if signal_id:
            logger.info(f"✅ سیگنال با ID {signal_id} ذخیره شد")
            return True
        else:
            logger.error(f"❌ save_signal_advanced مقدار None برگرداند")
            return False
    except Exception as e:
        logger.error(f"❌ خطا در save_signal_advanced: {e}", exc_info=True)
        return False

def main():
    logger.info("=" * 60)
    logger.info("🚀 شروع دیباگ ذخیره سیگنال")
    logger.info("=" * 60)
    
    # 1. بررسی دیتابیس
    logger.info("📌 مرحله 1: بررسی دیتابیس")
    try:
        init_db()
        logger.info("✅ init_db موفق")
    except Exception as e:
        logger.error(f"❌ init_db خطا: {e}")
        return
    
    # 2. تعداد پوزیشن‌های فعلی
    open_count = get_open_positions_count()
    logger.info(f"📊 تعداد پوزیشن‌های باز فعلی: {open_count}")
    
    # 3. شبیه‌سازی ذخیره برای چند سمبل
    symbols = ['BTC-USD', 'ETH-USD', 'ADA-USD']
    results = {}
    
    logger.info("📌 مرحله 2: شبیه‌سازی ذخیره سیگنال‌ها")
    for symbol in symbols:
        result = simulate_signal_save(symbol)
        results[symbol] = result
    
    # 4. گزارش نهایی
    logger.info("=" * 60)
    logger.info("📊 نتایج:")
    for symbol, result in results.items():
        status = "✅" if result else "❌"
        logger.info(f"{status} {symbol}: {'موفق' if result else 'ناموفق'}")
    
    # 5. تعداد نهایی پوزیشن‌ها
    final_count = get_open_positions_count()
    logger.info(f"📊 تعداد نهایی پوزیشن‌های باز: {final_count}")
    logger.info(f"📈 تغییر: {final_count - open_count}")

if __name__ == "__main__":
    main()

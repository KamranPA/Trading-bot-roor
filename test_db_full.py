#!/usr/bin/env python3
# ---------------------------------------------------------
# FILE: test_db_full.py
# توضیح: تست کامل اتصال و عملیات دیتابیس Supabase
# ---------------------------------------------------------
import os
import sys
import logging
import datetime
from dotenv import load_dotenv

# بارگذاری متغیرهای محیطی
load_dotenv()

# تنظیم لاگ کامل
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('db_test.log')
    ]
)
logger = logging.getLogger(__name__)

# اضافه کردن مسیر src به PATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import ماژول‌های پروژه
try:
    from database import (
        init_db, 
        save_signal_advanced, 
        get_open_positions,
        get_open_positions_count,
        get_total_closed_positions_count,
        get_performance_summary,
        log_scan_status,
        get_last_signal_for_pair,
        get_connection,
        _get_database_url
    )
    logger.info("✅ ماژول database با موفقیت بارگذاری شد")
except ImportError as e:
    logger.error(f"❌ خطا در بارگذاری ماژول database: {e}")
    sys.exit(1)

# ---------------------------------------------------------
# توابع تست
# ---------------------------------------------------------

def test_connection():
    """تست اتصال به دیتابیس"""
    logger.info("=" * 60)
    logger.info("🔍 تست ۱: بررسی اتصال به دیتابیس")
    
    try:
        # بررسی وجود DATABASE_URL
        url = _get_database_url()
        logger.info(f"✅ DATABASE_URL موجود است (با sslmode)")
        
        # تست اتصال مستقیم
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1 as test")
            result = cur.fetchone()
            logger.info(f"✅ اتصال موفق: {result}")
        conn.close()
        return True
    except Exception as e:
        logger.error(f"❌ خطای اتصال: {e}", exc_info=True)
        return False

def test_init_db():
    """تست ایجاد جدول‌ها"""
    logger.info("=" * 60)
    logger.info("🔍 تست ۲: ایجاد/بروزرسانی جدول‌ها")
    
    try:
        init_db()
        logger.info("✅ جدول‌ها با موفقیت ایجاد/بروزرسانی شدند")
        return True
    except Exception as e:
        logger.error(f"❌ خطا در init_db: {e}", exc_info=True)
        return False

def test_insert_signal():
    """تست درج سیگنال با داده‌های کامل"""
    logger.info("=" * 60)
    logger.info("🔍 تست ۳: درج سیگنال کامل")
    
    test_data = {
        'direction': 'LONG',
        'entry_price': 30000.0,
        'stop_loss': 29000.0,
        'tp1': 31000.0,
        'tp2': 32000.0,
        'swing_ref': 29500.0,
        'total_score': 75.5,
        'ai_score': 65.0,
        'rsi_score': 70.0,
        'adx_score': 80.0,
        'ema_score': 85.0,
        'feat_adx': 25.0,
        'feat_rsi': 55.0,
        'feat_rsi_momentum': 2.5,
        'feat_ema_deviation': 1.2,
        'feat_atr_percent': 0.8,
        'feat_trend_line': 0.5,
        'feat_body_ratio': 0.7
    }
    
    try:
        signal_id = save_signal_advanced('BTC-USD-TEST', **test_data)
        if signal_id:
            logger.info(f"✅ سیگنال با ID {signal_id} ذخیره شد")
            return signal_id
        else:
            logger.error("❌ save_signal_advanced مقدار None برگرداند")
            return None
    except Exception as e:
        logger.error(f"❌ خطا در save_signal_advanced: {e}", exc_info=True)
        return None

def test_insert_minimal_signal():
    """تست درج سیگنال با حداقل داده‌ها"""
    logger.info("=" * 60)
    logger.info("🔍 تست ۴: درج سیگنال حداقل")
    
    try:
        signal_id = save_signal_advanced(
            'ETH-USD-TEST',
            direction='SHORT',
            entry_price=2000.0,
            stop_loss=2100.0,
            tp1=1900.0,
            total_score=65.0
        )
        if signal_id:
            logger.info(f"✅ سیگنال حداقل با ID {signal_id} ذخیره شد")
            return signal_id
        else:
            logger.error("❌ save_signal_advanced (حداقل) مقدار None برگرداند")
            return None
    except Exception as e:
        logger.error(f"❌ خطا در save_signal_advanced (حداقل): {e}", exc_info=True)
        return None

def test_scan_log():
    """تست ثبت لاگ اسکن"""
    logger.info("=" * 60)
    logger.info("🔍 تست ۵: ثبت لاگ اسکن")
    
    try:
        log_scan_status(
            'TEST-PAIR',
            'SCANNED',
            total=85.5,
            ai=70.0,
            rsi=80.0,
            adx=75.0,
            ema=90.0
        )
        logger.info("✅ لاگ اسکن با موفقیت ثبت شد")
        return True
    except Exception as e:
        logger.error(f"❌ خطا در log_scan_status: {e}", exc_info=True)
        return False

def test_get_queries():
    """تست کوئری‌های خواندن"""
    logger.info("=" * 60)
    logger.info("🔍 تست ۶: کوئری‌های خواندن")
    
    try:
        # تعداد پوزیشن‌های باز
        open_count = get_open_positions_count()
        logger.info(f"✅ تعداد پوزیشن‌های باز: {open_count}")
        
        # لیست پوزیشن‌های باز
        open_positions = get_open_positions()
        logger.info(f"✅ تعداد رکوردهای باز: {len(open_positions)}")
        
        # آخرین سیگنال برای BTC
        last_signal = get_last_signal_for_pair('BTC-USD-TEST')
        if last_signal:
            logger.info(f"✅ آخرین سیگنال BTC: {last_signal}")
        else:
            logger.info("ℹ️ سیگنالی برای BTC-USD-TEST یافت نشد")
        
        # خلاصه عملکرد
        performance = get_performance_summary()
        logger.info(f"✅ خلاصه عملکرد: {performance}")
        
        return True
    except Exception as e:
        logger.error(f"❌ خطا در کوئری‌های خواندن: {e}", exc_info=True)
        return False

def test_bulk_insert():
    """تست درج چندگانه (برای بررسی محدودیت‌ها)"""
    logger.info("=" * 60)
    logger.info("🔍 تست ۷: درج چندگانه")
    
    symbols = ['BTC-USD', 'ETH-USD', 'ADA-USD', 'DOT-USD']
    success_count = 0
    
    for symbol in symbols:
        try:
            signal_id = save_signal_advanced(
                symbol,
                direction='LONG' if len(symbol) % 2 == 0 else 'SHORT',
                entry_price=100.0 + len(symbol) * 10,
                stop_loss=90.0 + len(symbol) * 10,
                tp1=110.0 + len(symbol) * 10,
                total_score=70.0 + len(symbol) * 2
            )
            if signal_id:
                logger.info(f"✅ سیگنال {symbol} با ID {signal_id} ذخیره شد")
                success_count += 1
            else:
                logger.warning(f"⚠️ ذخیره سیگنال {symbol} ناموفق بود")
        except Exception as e:
            logger.error(f"❌ خطا در ذخیره {symbol}: {e}")
    
    logger.info(f"✅ از {len(symbols)} درج، {success_count} موفق بود")
    return success_count > 0

def test_manual_sql():
    """تست دستی SQL برای بررسی دقیق‌تر"""
    logger.info("=" * 60)
    logger.info("🔍 تست ۸: اجرای دستی SQL")
    
    try:
        from database import _db
        
        with _db() as conn:
            with conn.cursor() as cur:
                # بررسی وجود جدول
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 
                        FROM information_schema.tables 
                        WHERE table_name = 'signals'
                    )
                """)
                exists = cur.fetchone()[0]
                logger.info(f"✅ جدول signals وجود دارد: {exists}")
                
                if exists:
                    # شمارش رکوردها
                    cur.execute("SELECT COUNT(*) FROM signals")
                    count = cur.fetchone()[0]
                    logger.info(f"✅ تعداد کل رکوردها در signals: {count}")
                    
                    # آخرین ۵ رکورد
                    cur.execute("""
                        SELECT id, pair, direction, entry_price, status, timestamp 
                        FROM signals 
                        ORDER BY id DESC 
                        LIMIT 5
                    """)
                    rows = cur.fetchall()
                    for row in rows:
                        logger.info(f"   📊 رکورد: {row}")
        
        return True
    except Exception as e:
        logger.error(f"❌ خطا در اجرای SQL دستی: {e}", exc_info=True)
        return False

# ---------------------------------------------------------
# اجرای اصلی
# ---------------------------------------------------------

def run_all_tests():
    """اجرای تمام تست‌ها"""
    logger.info("=" * 60)
    logger.info("🚀 شروع تست‌های کامل دیتابیس")
    logger.info("=" * 60)
    
    results = {}
    
    # تست‌ها به ترتیب
    results['connection'] = test_connection()
    if not results['connection']:
        logger.error("❌ اتصال برقرار نشد - ادامه تست‌ها ممکن است ناموفق باشند")
    
    results['init_db'] = test_init_db()
    results['insert_minimal'] = test_insert_minimal_signal()
    results['insert_full'] = test_insert_signal()
    results['scan_log'] = test_scan_log()
    results['queries'] = test_get_queries()
    results['bulk_insert'] = test_bulk_insert()
    results['manual_sql'] = test_manual_sql()
    
    # گزارش نهایی
    logger.info("=" * 60)
    logger.info("📊 گزارش نهایی تست‌ها:")
    logger.info("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
        if not passed:
            all_passed = False
    
    logger.info("=" * 60)
    if all_passed:
        logger.info("🎉 همه تست‌ها با موفقیت گذرانده شدند!")
    else:
        logger.warning("⚠️ برخی تست‌ها ناموفق بودند - لطفاً لاگ‌ها را بررسی کنید")
    
    # ذخیره نتایج در فایل
    with open('test_results.txt', 'w') as f:
        f.write(f"تاریخ اجرا: {datetime.datetime.now()}\n")
        f.write("=" * 60 + "\n")
        for test_name, passed in results.items():
            f.write(f"{'✅' if passed else '❌'} {test_name}\n")
        f.write("=" * 60 + "\n")
        f.write(f"موفقیت کلی: {'✅' if all_passed else '❌'}\n")
    
    logger.info("📝 نتایج در فایل test_results.txt ذخیره شد")
    return all_passed

# ---------------------------------------------------------
# اجرا
# ---------------------------------------------------------

if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("🛑 تست توسط کاربر متوقف شد")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {e}", exc_info=True)
        sys.exit(1)

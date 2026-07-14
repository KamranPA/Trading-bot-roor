# FILE PATH: momentum_bot.py (v1.0 - NEW)
# ---------------------------------------------------------------------------
# نقطه‌ی ورود روزانه‌ی استراتژی Daily Momentum (BTC/ETH، نگه‌داری ~۵ روزه).
# کاملاً جدا از main.py (سیستم TA چهارساعته‌ی قدیمی) — نه آن را صدا می‌زند
# نه جدول دیتابیسش را لمس می‌کند. اجرا: یک‌بار در روز (نه هر ۳۰ دقیقه).
#
# منطق هر اجرا:
#   1. init جدول momentum_positions (اگر نبود)
#   2. برای هر پوزیشن OPEN که planned_exit_date رسیده/گذشته: ببند + تلگرام
#   3. برای هر ارز (BTC/ETH) که پوزیشن باز ندارد: سیگنال جدید بررسی کن،
#      اگر بود، باز کن + تلگرام
# ---------------------------------------------------------------------------
import os
import sys
import logging
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from src import database, telegram_bot, momentum_strategy
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_and_close_expired_positions():
    """پوزیشن‌هایی که planned_exit_date رسیده را می‌بندد."""
    open_positions = database.get_all_open_momentum_positions()
    if not open_positions:
        logger.info("هیچ پوزیشن باز momentum برای بررسی وجود ندارد.")
        return

    today = date.today()
    for pos in open_positions:
        planned_exit = pos.get('planned_exit_date')
        if planned_exit is None or planned_exit > today:
            continue  # هنوز موعد بستن نرسیده

        pair = pos['pair']
        current_price = momentum_strategy.get_current_price(pair)
        if current_price is None:
            logger.warning(f"دریافت قیمت فعلی {pair} ناموفق — بستن به تعویق افتاد")
            continue

        entry_price = float(pos['entry_price'])
        direction = pos['direction']
        ret = (current_price - entry_price) / entry_price * 100
        pnl = ret if direction == 'LONG' else -ret

        success = database.close_momentum_position(pos['id'], current_price, today, pnl)
        if success:
            logger.info(f"✅ پوزیشن {pair} بسته شد | PnL: {pnl:.2f}%")
            try:
                telegram_bot.send_momentum_exit_notice(
                    pair, direction, entry_price, current_price, pnl,
                    pos.get('entry_date'), today
                )
            except Exception as e:
                logger.error(f"خطا در ارسال تلگرام بستن پوزیشن {pair}: {e}")
        else:
            logger.error(f"خطا در بستن پوزیشن {pair} (id={pos['id']})")


def check_for_new_signals():
    """برای هر ارز بدون پوزیشن باز، سیگنال جدید momentum بررسی می‌کند."""
    for symbol in momentum_strategy.MOMENTUM_SYMBOLS:
        existing = database.get_open_momentum_position(symbol)
        if existing is not None:
            logger.info(f"{symbol}: پوزیشن باز موجود است (از {existing.get('entry_date')}) — رد شد")
            continue

        signal = momentum_strategy.generate_momentum_signal(symbol)
        if signal is None:
            logger.info(f"{symbol}: سیگنالی صادر نشد")
            continue

        position_id = database.save_momentum_position(
            pair=signal['pair'], direction=signal['direction'],
            entry_price=signal['entry_price'], entry_date=signal['entry_date'],
            planned_exit_date=signal['planned_exit_date'],
            lookback_days=signal['lookback_days'], hold_days=signal['hold_days'],
            momentum_return_pct=signal['momentum_return_pct'],
        )
        if position_id:
            logger.info(f"✅ سیگنال جدید {symbol}: {signal['direction']} (id={position_id})")
            try:
                telegram_bot.format_and_send_momentum_signal(signal)
            except Exception as e:
                logger.error(f"خطا در ارسال تلگرام سیگنال {symbol}: {e}")
        else:
            logger.error(f"ذخیره‌ی سیگنال {symbol} ناموفق بود")


def run():
    logger.info("=" * 60)
    logger.info("🔄 اجرای روزانه‌ی Daily Momentum Bot (Signal-Only, بدون اجرای معامله)")
    logger.info(f"   نمادها: {momentum_strategy.MOMENTUM_SYMBOLS} | "
                f"LOOKBACK={momentum_strategy.LOOKBACK_DAYS}d | "
                f"HOLD={momentum_strategy.HOLD_DAYS}d")
    logger.info("=" * 60)

    try:
        database.init_momentum_table()
    except Exception as e:
        logger.error(f"خطا در init_momentum_table: {e}")
        return

    try:
        check_and_close_expired_positions()
    except Exception as e:
        logger.error(f"خطا در check_and_close_expired_positions: {e}", exc_info=True)

    try:
        check_for_new_signals()
    except Exception as e:
        logger.error(f"خطا در check_for_new_signals: {e}", exc_info=True)

    try:
        summary = database.get_momentum_performance_summary()
        logger.info(f"📊 خلاصه‌ی عملکرد تاکنون: {summary}")
    except Exception as e:
        logger.warning(f"خطا در خواندن خلاصه‌ی عملکرد: {e}")

    logger.info("✅ اجرای روزانه کامل شد.")


if __name__ == "__main__":
    run()

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


def check_open_positions():
    """
    ✅ هر پوزیشن باز را هر روز از دو جهت چک می‌کند:
      1. آیا امروز به سقف لیکویید شدن (بر اساس لوریج) رسیده؟ اگر بله،
         فوراً می‌بندد — حتی اگر تاریخ خروج برنامه‌ریزی‌شده نرسیده باشد.
      2. آیا تاریخ خروج برنامه‌ریزی‌شده رسیده/گذشته؟ اگر بله و لیکویید
         نشده، با قیمت بسته‌شدن امروز می‌بندد.
    این جایگزین check_and_close_expired_positions قدیمی است — چون آن
    نسخه فقط روز خروج را چک می‌کرد و ریسک لیکویید شدن میان‌راه (که با
    لوریج ۵ کاملاً واقعی است) را نادیده می‌گرفت.
    """
    open_positions = database.get_all_open_momentum_positions()
    if not open_positions:
        logger.info("هیچ پوزیشن باز momentum برای بررسی وجود ندارد.")
        return

    today = date.today()
    for pos in open_positions:
        pair = pos['pair']
        direction = pos['direction']
        entry_price = float(pos['entry_price'])
        position_size = float(pos.get('position_size_usd') or momentum_strategy.POSITION_SIZE_USD)
        leverage = float(pos.get('leverage') or momentum_strategy.LEVERAGE)
        liq_price = pos.get('liquidation_price')
        if liq_price is None:
            liq_price = momentum_strategy.get_liquidation_price(entry_price, direction, leverage)
        else:
            liq_price = float(liq_price)

        ohlc = momentum_strategy.get_current_day_ohlc(pair)
        if ohlc is None:
            logger.warning(f"دریافت OHLC روزانه‌ی {pair} ناموفق — بررسی امروز به تعویق افتاد")
            continue

        # ── ۱. بررسی ریسک لیکویید شدن (اولویت با این است) ──────────────────
        liquidated = False
        if direction == 'LONG' and ohlc['low'] <= liq_price:
            liquidated = True
        elif direction == 'SHORT' and ohlc['high'] >= liq_price:
            liquidated = True

        planned_exit = pos.get('planned_exit_date')
        reached_exit_date = planned_exit is not None and planned_exit <= today

        if not liquidated and not reached_exit_date:
            continue  # هنوز نه لیکویید شده نه موعد خروج رسیده — کاری نکن

        if liquidated:
            close_price = liq_price
            price_pnl_pct = -100.0 / leverage  # ضرر کامل مارجین (تقریبی)
            reason = "LIQUIDATED"
        else:
            close_price = ohlc['close']
            ret = (close_price - entry_price) / entry_price * 100
            price_pnl_pct = ret if direction == 'LONG' else -ret
            reason = "TIME_EXIT"

        pnl_usd = momentum_strategy.compute_leveraged_pnl_usd(price_pnl_pct, position_size, leverage)

        success = database.close_momentum_position(
            pos['id'], close_price, today, price_pnl_pct, pnl_usd, liquidated
        )
        if success:
            tag = "🔴 لیکویید شد" if liquidated else "بسته شد"
            logger.info(f"✅ پوزیشن {pair} {tag} | PnL قیمت: {price_pnl_pct:.2f}% | "
                        f"PnL دلاری: ${pnl_usd:.2f}")
            try:
                telegram_bot.send_momentum_exit_notice(
                    pair, direction, entry_price, close_price, price_pnl_pct,
                    pos.get('entry_date'), today, pnl_usd=pnl_usd, liquidated=liquidated
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
            position_size_usd=signal['position_size_usd'], leverage=signal['leverage'],
            liquidation_price=signal['liquidation_price'],
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
        check_open_positions()
    except Exception as e:
        logger.error(f"خطا در check_open_positions: {e}", exc_info=True)

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

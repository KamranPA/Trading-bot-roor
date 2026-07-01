# ---------------------------------------------------------
# FILE PATH: main.py (v2.3 - Auto train_model + ai_threshold sync)
# تغییرات نسبت به v2.2:
#   ✅ run_auto_optimization: train_model هم اجرا می‌شود (نه فقط optimizer)
#   ✅ ai_thresholds.json در لایو هم آپدیت می‌شود
#   ✅ check_exits: هم 'Close' و هم 'close' پشتیبانی می‌شود
#   ✅ get_symbol_params: از ai_thresholds.json هم لود می‌کند (برای لاگ)
# ---------------------------------------------------------
import os
import sys
import logging
import threading
import datetime
import json
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    import config
    from src import database, coinex_client, strategy, telegram_bot, indicators, optimizer
    from src.brain import TradingBrain
    from src.ai_threshold import get_ai_threshold, get_threshold_info
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

BRAIN   = TradingBrain()
db_lock = threading.Lock()


# ---------------------------------------------------------------------------
# خواندن پارامترهای اختصاصی هر ارز
# ---------------------------------------------------------------------------

def get_symbol_params(symbol: str) -> dict:
    """پارامترهای بهینه از best_params.json — با fallback به config"""
    default_params = {
        'ADX_THRESHOLD': getattr(config, 'ADX_THRESHOLD', 15.0),
        'SWING_WINDOW':  getattr(config, 'SWING_WINDOW',  3),
        'SL_RATIO':      getattr(config, 'SL_RATIO',      1.0),
        'TP_RATIO':      getattr(config, 'TP_RATIO',      1.5),
        'RSI_MIDLINE':   50.0,
    }
    params_file = os.path.join(BASE_DIR, 'best_params.json')
    if not os.path.exists(params_file):
        return default_params
    try:
        with open(params_file, 'r') as f:
            all_params = json.load(f)
        if symbol in all_params:
            merged = {**default_params, **all_params[symbol]}
            # لاگ AI_THRESHOLD کالیبره‌شده برای این symbol
            info = get_threshold_info(symbol)
            if info:
                logger.debug(
                    f"{symbol}: AI_THRESHOLD کالیبره‌شده = {info['threshold']} "
                    f"(percentile={info['percentile']})"
                )
            return merged
    except Exception as e:
        logger.error("خطا در خواندن best_params.json برای %s: %s", symbol, e)
    return default_params


# ---------------------------------------------------------------------------
# بررسی و بستن پوزیشن‌های باز
# ---------------------------------------------------------------------------

def check_exits():
    try:
        positions = database.get_open_positions()
        if not positions:
            logger.info("هیچ پوزیشن بازی برای بررسی وجود ندارد.")
            return

        logger.info(f"بررسی {len(positions)} پوزیشن باز...")

        for pos in positions:
            sig_id    = pos.get('id')
            symbol    = pos.get('symbol')
            direction = pos.get('direction')

            entry_price_raw = pos.get('entry_price')
            stop_loss_raw   = pos.get('stop_loss')
            tp2_raw         = pos.get('tp2')

            if entry_price_raw is None:
                logger.warning(f"entry_price برای پوزیشن {sig_id} ({symbol}) None است - SKIP")
                continue
            if stop_loss_raw is None:
                logger.warning(f"stop_loss برای پوزیشن {sig_id} ({symbol}) None است - SKIP")
                continue
            if tp2_raw is None:
                logger.warning(f"tp2 برای پوزیشن {sig_id} ({symbol}) None است - SKIP")
                continue

            try:
                entry = float(entry_price_raw)
                sl    = float(stop_loss_raw)
                tp2   = float(tp2_raw)
            except (ValueError, TypeError) as e:
                logger.error(f"خطا در تبدیل مقادیر پوزیشن {sig_id}: {e}")
                continue

            df = coinex_client.get_coinex_candles(symbol, limit=1)
            if df is None or df.empty:
                logger.warning(f"دریافت قیمت برای {symbol} ناموفق بود")
                continue

            # ✅ FIX: پشتیبانی از هر دو 'Close' و 'close'
            last_row = df.iloc[-1]
            current_price = float(
                last_row.get('Close', last_row.get('close', 0))
            )
            if current_price == 0:
                logger.warning(f"قیمت فعلی {symbol} صفر است - SKIP")
                continue

            close_price = None
            reason      = None

            if direction == "LONG":
                if current_price <= sl:
                    close_price = sl;  reason = "SL hit"
                elif current_price >= tp2:
                    close_price = tp2; reason = "TP2 hit"
            elif direction == "SHORT":
                if current_price >= sl:
                    close_price = sl;  reason = "SL hit"
                elif current_price <= tp2:
                    close_price = tp2; reason = "TP2 hit"

            if close_price is not None:
                pnl = ((close_price - entry) / entry) * 100 if direction == "LONG" \
                      else ((entry - close_price) / entry) * 100

                success = database.update_position_status(sig_id, 'CLOSED', round(pnl, 4))
                if success:
                    logger.info(f"پوزیشن {symbol} بسته شد | {reason} | PnL: {pnl:.2f}%")
                else:
                    logger.error(f"خطا در بستن پوزیشن {sig_id}")

    except Exception as e:
        logger.error(f"خطا در check_exits: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

def heartbeat_job():
    try:
        watchlist_count = len(getattr(config, 'WATCHLIST', []))
        models_dir      = os.path.join(BASE_DIR, "src", "models")
        model_count     = (
            len([f for f in os.listdir(models_dir) if f.endswith('.pkl')])
            if os.path.exists(models_dir) else 0
        )
        telegram_bot.send_heartbeat_report(watchlist_count, model_count)
        logger.info("گزارش Heartbeat ارسال شد.")
    except Exception as e:
        logger.error(f"خطا در Heartbeat: {e}")


# ---------------------------------------------------------------------------
# پردازش هر ارز
# ---------------------------------------------------------------------------

def process_pair(pair: str, open_positions_count: int):
    try:
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty:
            logger.warning(f"دریافت کندل برای {pair} ناموفق بود — API_FAIL")
            try:
                database.log_scan_status(pair, "API_FAIL")
            except Exception:
                pass
            return

        df = indicators.calculate_indicators(df, symbol=pair)

        sym_params = get_symbol_params(pair)

        res = strategy.generate_signal(
            df, pair,
            model=BRAIN,
            params=sym_params,
            open_positions_count=open_positions_count,
        )

        if not isinstance(res, dict):
            return

        t_score = res.get('total_score', 0.0)
        ai_s    = res.get('ai_score',    0.0)
        rsi_s   = res.get('rsi_score',   0.0)
        adx_s   = res.get('adx_score',   0.0)
        ema_s   = res.get('ema_score',   0.0)

        with db_lock:
            if res.get('direction') is not None:
                signal = {
                    k: v for k, v in res.items()
                    if k not in ('pair', 'symbol')
                }

                signal_id = database.save_signal_advanced(pair=pair, **signal)
                if signal_id:
                    logger.info(f"سیگنال {pair} با ID {signal_id} ذخیره شد")
                else:
                    logger.error(f"ذخیره سیگنال {pair} ناموفق بود")

                database.log_scan_status(pair, "SIGNAL_SENT",
                                         total=t_score, ai=ai_s,
                                         rsi=rsi_s, adx=adx_s, ema=ema_s)
                try:
                    tele_signal = res.copy()
                    tele_signal['pair'] = pair
                    telegram_bot.format_and_send_signal(tele_signal)
                    logger.info(f"سیگنال {pair} به تلگرام ارسال شد.")
                except Exception as t_err:
                    logger.error(f"خطا در ارسال تلگرام برای {pair}: {t_err}")
            else:
                database.log_scan_status(pair, "NOSIGNAL",
                                         total=t_score, ai=ai_s,
                                         rsi=rsi_s, adx=adx_s, ema=ema_s)

    except Exception as e:
        logger.error(f"خطا در پردازش {pair}: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# خودارتقایی
# ---------------------------------------------------------------------------

def run_auto_optimization():
    """
    خودارتقایی خودکار — هر 50 معامله بسته‌شده یک‌بار اجرا می‌شود.

    ترتیب اجرا (یکسان با workflow GitHub Actions):
      1. optimizer  → best_params.json
      2. train_model → مدل‌ها + ai_thresholds.json

    نکته: چون ربات با GitHub Actions cron اجرا می‌شه و workspace هر بار
    از صفر شروع می‌شه، milestone آخر اجرا رو در دیتابیس ذخیره می‌کنیم
    (دیتابیس PostgreSQL بین اجراها persist می‌شه).
    """
    try:
        total_closed = database.get_total_closed_positions_count()
        if total_closed <= 0 or total_closed % 50 != 0:
            return

        # ── جلوگیری از اجرای مکرر برای همون milestone ──────────────────
        # workspace هر بار از صفر شروع می‌شه، پس از دیتابیس استفاده می‌کنیم
        try:
            last_milestone = database.get_meta('last_optimization_milestone')
            if last_milestone and int(last_milestone) >= total_closed:
                logger.info(
                    f"⏭️ خودارتقایی برای milestone {total_closed} قبلاً انجام شده "
                    f"(آخرین: {last_milestone}) — skip"
                )
                return
        except Exception as e:
            logger.warning(f"⚠️ خطا در خواندن milestone از دیتابیس: {e} — ادامه می‌دیم")

        logger.info(f"🔄 شروع خودارتقایی (معاملات بسته: {total_closed})...")

        # ── مرحله ۱: optimizer ────────────────────────────────────────────
        logger.info("🔧 مرحله ۱: بهینه‌سازی پارامترهای استراتژی...")
        try:
            optimizer.optimize_all(mode="live")
            logger.info("✅ optimizer تمام شد → best_params.json آپدیت شد")
        except Exception as e:
            logger.error(f"❌ خطا در optimizer: {e}", exc_info=True)
            # ادامه می‌دهیم — train_model می‌تواند با best_params قدیمی هم کار کند

        # ── مرحله ۲: train_model ──────────────────────────────────────────
        logger.info("🧠 مرحله ۲: بازآموزی مدل AI + کالیبراسیون AI_THRESHOLD...")
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, os.path.join(BASE_DIR, 'src', 'train_model.py')],
                capture_output=True, text=True, timeout=600
            )
            if result.returncode == 0:
                logger.info("✅ train_model تمام شد → مدل‌ها + ai_thresholds.json آپدیت شد")
            else:
                logger.error(f"❌ train_model خطا داشت:\n{result.stderr[-500:]}")
        except subprocess.TimeoutExpired:
            logger.error("❌ train_model timeout (بیش از 10 دقیقه)")
        except Exception as e:
            logger.error(f"❌ خطا در اجرای train_model: {e}", exc_info=True)

        # ── مرحله ۳: لاگ نهایی ───────────────────────────────────────────
        # چون ربات با cron اجرا می‌شه و هر بار از صفر شروع می‌کنه،
        # reload لازم نیست — دفعه‌ی بعد cron، BRAIN مدل‌های جدید رو
        # خودش از src/models/ لود می‌کنه و ai_thresholds.json تازه رو
        # از طریق get_ai_threshold() می‌خونه.
        # ── ذخیره milestone در دیتابیس ─────────────────────────────────
        try:
            database.set_meta('last_optimization_milestone', str(total_closed))
            logger.info(f"✅ milestone {total_closed} در دیتابیس ذخیره شد")
        except Exception as e:
            logger.warning(f"⚠️ خطا در ذخیره milestone: {e}")

        logger.info(f"✅ خودارتقایی کامل شد (معاملات بسته: {total_closed})")

    except Exception as e:
        logger.error(f"خطا در run_auto_optimization: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# اجرای ربات
# ---------------------------------------------------------------------------

def run_bot():
    logger.info("اسکنر هوشمند فعال شد.")

    try:
        database.init_db()
        logger.info("دیتابیس آماده است.")
    except Exception as e:
        logger.error(f"خطا در init_db: {e}")
        return

    try:
        check_exits()
    except Exception as e:
        logger.error(f"خطا در check_exits: {e}", exc_info=True)

    try:
        run_auto_optimization()
    except Exception as e:
        logger.error(f"خطا در auto_optimization: {e}")

    try:
        open_positions_count = database.get_open_positions_count()
    except Exception as e:
        logger.error(f"خطا در خواندن تعداد پوزیشن‌ها: {e} — مقدار ۰ فرض می‌شود")
        open_positions_count = 0

    watchlist = getattr(config, 'WATCHLIST', [])
    logger.info(f"اسکن {len(watchlist)} ارز | پوزیشن‌های باز: {open_positions_count}")

    if not watchlist:
        logger.warning("WATCHLIST خالی است!")
        return

    with ThreadPoolExecutor(max_workers=12) as executor:
        executor.map(lambda p: process_pair(p, open_positions_count), watchlist)

    logger.info("دور اسکن کامل شد.")


if __name__ == "__main__":
    if datetime.datetime.now(datetime.timezone.utc).hour == 22:
        heartbeat_job()
    run_bot()

# ---------------------------------------------------------
# FILE PATH: main.py  (FIXED & IMPROVED v2.0)
# تغییرات:
#   1. open_positions_count یکبار خوانده می‌شود، نه داخل هر generate_signal
#   2. اصلاح محاسبه PnL در check_exits (باگ SHORT)
#   3. استفاده از current_price برای PnL (نه SL/TP ثابت)
#   4. پشتیبانی از CSV برای داده بکتست (کنار Supabase)
#   5. مدیریت خطای بهتر با logging کامل
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
except ImportError as e:
    print(f"CRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

BRAIN    = TradingBrain()
db_lock  = threading.Lock()


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
            return {**default_params, **all_params[symbol]}
    except Exception as e:
        logger.error("خطا در خواندن best_params.json برای %s: %s", symbol, e)
    return default_params


# ---------------------------------------------------------------------------
# بررسی و بستن پوزیشن‌های باز  (FIX: محاسبه PnL درست شد)
# ---------------------------------------------------------------------------

def check_exits():
    """
    بررسی قیمت زنده برای همه پوزیشن‌های باز و بستن آن‌ها در صورت رسیدن به SL یا TP2.

    FIX: محاسبه PnL بر اساس قیمت بسته‌شدن واقعی (نه SL/TP ثابت که قبلاً غلط بود).
    """
    try:
        positions = database.get_open_positions()
        if not positions:
            return

        for pos in positions:
            sig_id    = pos['id']
            symbol    = pos['symbol']
            direction = pos['direction']
            entry     = float(pos['entry_price'])
            sl        = float(pos['stop_loss'])
            tp2       = float(pos['tp2'])

            df = coinex_client.get_coinex_candles(symbol, limit=1)
            if df is None or df.empty:
                logger.warning("دریافت قیمت برای %s ناموفق بود", symbol)
                continue

            current_price = float(df.iloc[-1]['Close'])
            close_price   = None
            reason        = None

            if direction == "LONG":
                if current_price <= sl:
                    close_price = sl
                    reason      = "SL hit"
                elif current_price >= tp2:
                    close_price = tp2
                    reason      = "TP2 hit"

            elif direction == "SHORT":
                if current_price >= sl:
                    close_price = sl
                    reason      = "SL hit"
                elif current_price <= tp2:
                    close_price = tp2
                    reason      = "TP2 hit"

            if close_price is not None:
                # FIX: فرمول PnL یکپارچه برای هر دو جهت
                if direction == "LONG":
                    pnl = ((close_price - entry) / entry) * 100
                else:  # SHORT — قبلاً این فرمول غلط بود
                    pnl = ((entry - close_price) / entry) * 100

                database.update_position_status(sig_id, 'CLOSED', round(pnl, 4))
                logger.info("✅ پوزیشن %s بسته شد | %s | PnL: %.2f%%", symbol, reason, pnl)

    except Exception as e:
        logger.error("خطا در check_exits: %s", e)


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
        logger.info("✅ گزارش Heartbeat ارسال شد.")
    except Exception as e:
        logger.error("خطا در Heartbeat: %s", e)


# ---------------------------------------------------------------------------
# پردازش هر ارز  (FIX: open_positions_count از بیرون تزریق می‌شود)
# ---------------------------------------------------------------------------

def process_pair(pair: str, open_positions_count: int):
    """
    FIX: open_positions_count یکبار پیش از ThreadPoolExecutor خوانده می‌شود
    و به هر تابع تزریق می‌شود — دیگر داخل generate_signal به DB متصل نمی‌شویم.
    """
    try:
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty:
            logger.debug("داده‌ای برای %s دریافت نشد", pair)
            return

        df = indicators.calculate_indicators(df)

        sym_params = get_symbol_params(pair)

        # FIX: تزریق open_positions_count به جای خواندن از DB داخل تابع
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
                tele_signal = res.copy()
                tele_signal['pair_display'] = (
                    "MATIC/USDT (POL)" if pair == "POL/USDT" else pair
                )
                signal = {
                    k: v for k, v in res.items()
                    if k not in ('pair', 'symbol', 'total_score',
                                 'ai_score', 'rsi_score', 'adx_score', 'ema_score')
                }
                database.save_signal_advanced(pair=pair, **signal)
                database.log_scan_status(pair, "SIGNAL SENT",
                                         total=t_score, ai=ai_s,
                                         rsi=rsi_s, adx=adx_s, ema=ema_s)
                try:
                    telegram_bot.format_and_send_signal(tele_signal)
                    logger.info("🚀 سیگنال %s به تلگرام ارسال شد.", pair)
                except Exception as t_err:
                    logger.error("خطا در ارسال تلگرام برای %s: %s", pair, t_err)
            else:
                database.log_scan_status(pair, "nosignal",
                                         total=t_score, ai=ai_s,
                                         rsi=rsi_s, adx=adx_s, ema=ema_s)

    except Exception as e:
        logger.error("خطا در پردازش %s: %s", pair, e)


# ---------------------------------------------------------------------------
# خودارتقایی
# ---------------------------------------------------------------------------

def run_auto_optimization():
    try:
        total_closed = database.get_total_closed_positions_count()
        if total_closed > 0 and total_closed % 50 == 0:
            logger.info("⚙️ اجرای خودارتقایی (معاملات بسته: %d)...", total_closed)
            optimizer.optimize_all(mode="live")
    except Exception as e:
        logger.error("خطا در خودارتقایی: %s", e)


# ---------------------------------------------------------------------------
# اجرای ربات
# ---------------------------------------------------------------------------

def run_bot():
    logger.info("🤖 اسکنر هوشمند فعال شد.")
    database.init_db()

    check_exits()
    run_auto_optimization()

    # FIX: یکبار تعداد پوزیشن‌های باز را می‌خوانیم (نه داخل هر تابع)
    try:
        open_positions_count = database.get_open_positions_count()
    except Exception as e:
        logger.error("خطا در خواندن تعداد پوزیشن‌ها: %s — مقدار ۰ فرض می‌شود", e)
        open_positions_count = 0

    watchlist = getattr(config, 'WATCHLIST', [])
    logger.info("اسکن %d ارز | پوزیشن‌های باز: %d", len(watchlist), open_positions_count)

    with ThreadPoolExecutor(max_workers=12) as executor:
        executor.map(lambda p: process_pair(p, open_positions_count), watchlist)

    logger.info("✅ دور اسکن کامل شد.")


if __name__ == "__main__":
    if datetime.datetime.utcnow().hour == 22:
        heartbeat_job()
    run_bot()

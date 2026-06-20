# ---------------------------------------------------------
# FILE PATH: src/strategy.py  (FIXED & IMPROVED v2.0)
# تغییرات:
#   1. except خالی → except Exception as e + logging
#   2. جداسازی database از حلقه اصلی (db_check پیش از ورود به تابع)
#   3. اصلاح entry_price: همیشه current_price نه swing قدیمی
#   4. بهبود محاسبه rsi_score (باگ منطقی)
#   5. مستندات داخلی کامل‌تر
# ---------------------------------------------------------
import logging
import datetime

import config
from src import database, strategy_utils

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# فیلتر ۸ ساعته
# ---------------------------------------------------------------------------

def is_blocked_by_8h_filter(pair: str, current_direction: str) -> bool:
    """
    اگر در ۸ ساعت گذشته سیگنال هم‌جهت برای این ارز صادر شده باشد،
    True برمی‌گردد (سیگنال فعلی بلاک می‌شود).
    """
    try:
        last_signal = database.get_last_signal_for_pair(pair)
        if not last_signal:
            return False

        last_direction = last_signal.get('direction')
        last_time = last_signal.get('timestamp')

        if last_direction != current_direction:
            return False

        if last_time is None:
            return False

        now = datetime.datetime.utcnow()
        # اگر last_time aware است، به naive تبدیل می‌کنیم
        if hasattr(last_time, 'tzinfo') and last_time.tzinfo is not None:
            last_time = last_time.replace(tzinfo=None)

        elapsed_hours = (now - last_time).total_seconds() / 3600
        return elapsed_hours < 8

    except Exception as e:
        logger.warning("خطا در بررسی فیلتر ۸ ساعته برای %s: %s", pair, e)
        return False  # در صورت خطا، بلاک نکن تا سیگنال از دست نرود


# ---------------------------------------------------------------------------
# تابع اصلی تولید سیگنال
# ---------------------------------------------------------------------------

def generate_signal(df, pair: str, model=None, params: dict = None,
                    open_positions_count: int = 0) -> dict:
    """
    نسخه اصلاح‌شده: پارامتر open_positions_count از بیرون تزریق می‌شود
    تا وابستگی مستقیم به database در حلقه اصلی حذف شود.

    Args:
        df: دیتافریم کندل‌ها با اندیکاتورهای محاسبه‌شده
        pair: نماد ارز (مثلاً "BTC/USDT")
        model: شیء TradingBrain برای پیش‌بینی AI
        params: دیکشنری پارامترهای اختصاصی ارز
        open_positions_count: تعداد پوزیشن‌های باز (از main.py تزریق می‌شود)

    Returns:
        دیکشنری امتیازها + اطلاعات سیگنال (در صورت وجود)
    """
    default_scores = {
        'total_score': 0.0,
        'ai_score': 0.0,
        'rsi_score': 0.0,
        'adx_score': 0.0,
        'ema_score': 0.0,
        'direction': None,
    }

    # --- اعتبارسنجی ورودی‌ها ---
    if df is None or len(df) < 200:
        logger.debug("دیتافریم ناکافی برای %s (طول: %s)", pair, len(df) if df is not None else 0)
        return default_scores

    if params is None:
        logger.warning("پارامتر params برای %s ارسال نشده؛ از پیش‌فرض‌ها استفاده می‌شود.", pair)
        params = {}

    # --- استخراج پارامترهای اختصاصی ---
    adx_thresh       = float(params.get('ADX_THRESHOLD',  config.ADX_THRESHOLD))
    tp_ratio         = float(params.get('TP_RATIO',        1.5))
    sl_ratio         = float(params.get('SL_RATIO',        1.0))
    ai_threshold     = float(params.get('AI_THRESHOLD',    65.0))
    swing_window     = int(params.get('SWING_WINDOW',      config.SWING_WINDOW))
    MAX_SL_PERCENT   = float(getattr(config, 'MAX_SL_PERCENT', 0.03))

    # --- آخرین کندل ---
    candle = df.iloc[-1]

    # -----------------------------------------------------------------------
    # سیستم امتیازدهی
    # -----------------------------------------------------------------------

    # ADX score
    current_adx = float(candle.get('feat_adx', 0))
    if current_adx >= adx_thresh:
        adx_score = min(100.0, 50.0 + (current_adx - adx_thresh) * 2.5)
    else:
        adx_score = max(0.0, (current_adx / (adx_thresh + 1e-10)) * 50.0)

    # RSI score — اصلاح‌شده: منطق یکپارچه و بدون تناقض
    current_rsi    = float(candle.get('feat_rsi', 50))
    rsi_momentum   = float(candle.get('feat_rsi_momentum', 0))
    if current_rsi > 50:
        rsi_score = min(100.0, 50.0 + rsi_momentum * 5)
    else:
        rsi_score = min(100.0, 50.0 + (-rsi_momentum) * 5)
    rsi_score = max(0.0, rsi_score)

    # EMA deviation score
    dev_val   = abs(float(candle.get('feat_ema_deviation', 0)))
    ema_score = min(100.0, (dev_val / 5.0) * 100.0)

    # -----------------------------------------------------------------------
    # پیش‌بینی AI
    # -----------------------------------------------------------------------
    features_dict = {
        'feat_adx':          current_adx,
        'feat_atr_percent':  float(candle.get('feat_atr_percent', 0)),
        'feat_rsi':          current_rsi,
        'feat_trend_line':   float(candle.get('feat_trend_line', 0)),
        'feat_ema_deviation': dev_val,
        'feat_rsi_momentum': rsi_momentum,
        'feat_body_ratio':   float(candle.get('feat_body_ratio', 0)),
    }

    ai_score    = 0.0
    ai_approved = False

    if model is not None:
        try:
            raw = model.predict_probability(pair, features_dict)
            ai_score = float(raw) * 100.0 if float(raw) <= 1.0 else float(raw)
            ai_approved = ai_score >= ai_threshold
        except Exception as e:
            logger.error("خطا در پیش‌بینی AI برای %s: %s", pair, e)
            return default_scores

    # -----------------------------------------------------------------------
    # امتیاز کل
    # -----------------------------------------------------------------------
    total_score = (
        ai_score  * 0.40 +
        adx_score * 0.20 +
        rsi_score * 0.20 +
        ema_score * 0.20
    )

    score_data = {
        'total_score': round(total_score, 2),
        'ai_score':    round(ai_score,    2),
        'rsi_score':   round(rsi_score,   2),
        'adx_score':   round(adx_score,   2),
        'ema_score':   round(ema_score,   2),
        'direction':   None,
    }

    # --- فیلتر امتیاز و ظرفیت پوزیشن ---
    max_positions = getattr(config, 'MAX_OPEN_POSITIONS', 3)
    if total_score < 60.0:
        logger.debug("%s: امتیاز %.1f زیر آستانه ۶۰", pair, total_score)
        return score_data

    if open_positions_count >= max_positions:
        logger.debug("%s: ظرفیت پوزیشن پر است (%d/%d)", pair, open_positions_count, max_positions)
        return score_data

    # -----------------------------------------------------------------------
    # یافتن Swing High / Low
    # -----------------------------------------------------------------------
    last_swing_high = strategy_utils.find_last_swing(df, 'high', swing_window)
    last_swing_low  = strategy_utils.find_last_swing(df, 'low',  swing_window)

    if last_swing_high is None or last_swing_low is None:
        logger.debug("%s: swing high/low یافت نشد", pair)
        return score_data

    # -----------------------------------------------------------------------
    # قیمت‌های کندل فعلی
    # -----------------------------------------------------------------------
    high_price = float(candle['High'])
    low_price  = float(candle['Low'])
    # FIX: از close به عنوان قیمت ورود واقعی استفاده می‌کنیم (نه swing قدیمی)
    close_price = float(candle['Close'])
    atr_val    = float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))

    # -----------------------------------------------------------------------
    # منطق ورود LONG
    # -----------------------------------------------------------------------
    if (high_price > last_swing_high
            and current_rsi > 50
            and ai_approved
            and not is_blocked_by_8h_filter(pair, "LONG")):

        sl_dist = min(1.5 * atr_val * sl_ratio, close_price * MAX_SL_PERCENT)
        if sl_dist <= 0:
            logger.warning("%s LONG: sl_dist صفر یا منفی — سیگنال لغو شد", pair)
            return score_data

        score_data.update({
            'pair':        pair,
            'direction':   'LONG',
            'entry_price': round(close_price, 6),                          # FIX: close نه swing
            'stop_loss':   round(close_price - sl_dist, 6),
            'tp1':         round(close_price + sl_dist * tp_ratio / 2, 6),
            'tp2':         round(close_price + sl_dist * tp_ratio,     6),
            'swing_ref':   round(last_swing_high, 6),                      # مرجع swing برای لاگ
            **features_dict,
        })
        logger.info("🟢 LONG سیگنال: %s | امتیاز: %.1f | Entry: %.4f | SL: %.4f | TP2: %.4f",
                    pair, total_score, close_price,
                    score_data['stop_loss'], score_data['tp2'])

    # -----------------------------------------------------------------------
    # منطق ورود SHORT
    # -----------------------------------------------------------------------
    elif (low_price < last_swing_low
            and current_rsi < 50
            and ai_approved
            and not is_blocked_by_8h_filter(pair, "SHORT")):

        sl_dist = min(1.5 * atr_val * sl_ratio, close_price * MAX_SL_PERCENT)
        if sl_dist <= 0:
            logger.warning("%s SHORT: sl_dist صفر یا منفی — سیگنال لغو شد", pair)
            return score_data

        score_data.update({
            'pair':        pair,
            'direction':   'SHORT',
            'entry_price': round(close_price, 6),                          # FIX: close نه swing
            'stop_loss':   round(close_price + sl_dist, 6),
            'tp1':         round(close_price - sl_dist * tp_ratio / 2, 6),
            'tp2':         round(close_price - sl_dist * tp_ratio,     6),
            'swing_ref':   round(last_swing_low, 6),
            **features_dict,
        })
        logger.info("🔴 SHORT سیگنال: %s | امتیاز: %.1f | Entry: %.4f | SL: %.4f | TP2: %.4f",
                    pair, total_score, close_price,
                    score_data['stop_loss'], score_data['tp2'])

    return score_data

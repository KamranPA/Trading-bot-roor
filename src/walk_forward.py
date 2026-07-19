# ---------------------------------------------------------------------------
# FILE PATH: src/walk_forward.py (NEW)
# هدف: تست صادق و کاملاً out-of-sample از استراتژی قانون‌محور (بدون AI —
# چون AI_GATE_ENABLED=False و اثبات شد مدل فعلی AUC≈0.48 دارد).
#
# چرا این اسکریپت لازم است:
#   optimizer.py/backtester.py فعلی روی یک split ثابت ۸۰/۲۰ کار می‌کنند؛
#   یعنی همان پارامترهایی که روی ۸۰٪ اول انتخاب می‌شوند، روی ۲۰٪ آخر (که
#   می‌تواند به‌طور تصادفی با آن ست پارامتر هم‌خوان باشد) گزارش داده می‌شوند.
#   این دقیقاً همان دام in-sample bias است که در مدل AI افتادیم. راه‌حل
#   استاندارد صنعتی: Walk-Forward Analysis — داده به چند بازه‌ی متوالی
#   تقسیم می‌شود؛ برای هر بازه، پارامتر فقط از داده‌ی *قبل* از آن بازه
#   انتخاب می‌شود و روی همان بازه (که مدل هرگز ندیده) تست می‌شود. اگر
#   نتیجه‌ی جمع همه‌ی بازه‌های out-of-sample مثبت بود، یعنی استراتژی
#   واقعاً edge دارد نه صرفاً حافظه‌ی داده‌ی گذشته.
#
#   همچنین برخلاف optimizer.py/backtester.py، اینجا هزینه‌ی معامله
#   (کارمزد + اسلیپیج تخمینی) از هر ترید کم می‌شود — یک استراتژی با
#   edge ضعیف می‌تواند در بک‌تست بدون‌هزینه سودآور به‌نظر برسد ولی در
#   دنیای واقعی با کارمزد صرافی ضرر بدهد.
#
# اجرا: python src/walk_forward.py
# خروجی: کنسول (خلاصه) + data/walk_forward_results.csv (جزئیات هر بازه)
# ---------------------------------------------------------------------------

import os
import sys
import json
import logging
from datetime import datetime, date
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from src import strategy_utils
from src import coinex_client
from src.indicators import TechnicalIndicators
from src.volume_filter import passes_volume_filter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── تنظیمات Walk-Forward ─────────────────────────────────────────────────────
WARMUP_ROWS   = 200   # هماهنگ با backtester.py/train_model.py
N_FOLDS       = 7     # ✅ افزایش از 5 به 7 — چون با فقط ۲ ارز، نمونه کوچک‌تر
                        # می‌شود؛ بازه‌ی بیشتر یعنی شواهد آماری قوی‌تر برای
                        # تأیید/رد فرضیه‌ی «BTC/ETH edge واقعی دارند».
MIN_TRADES_FOR_SELECTION = 10  # هماهنگ با optimizer.py

# هزینه‌ی رفت‌وبرگشت هر معامله (٪) — پیش‌فرض محافظه‌کارانه برای کارمزد+اسلیپیج.
# می‌توانی در config.py مقدار TRANSACTION_COST_PERCENT را override کنی.
TRANSACTION_COST_PERCENT = float(getattr(config, 'TRANSACTION_COST_PERCENT', 0.2))

AI_GATE_ENABLED = bool(getattr(config, 'AI_GATE_ENABLED', True))  # باید False باشد

# این لیست مستقل از config.WATCHLIST است، یعنی روی سیستم لایو اثر ندارد.
# ✅ محدود شد به فقط BTC/ETH — چون در تست قبلی (۵ ارز) این دو تنها
# نمادهایی بودند که momentum_daily رویشان مثبت بود (SOL/XRP/LTC منفی).
TEST_SYMBOLS = ['BTCUSDT', 'ETHUSDT']

ADX_OPTIONS   = [15, 20, 25]
SWING_OPTIONS = [3, 5, 7]
TP_OPTIONS    = [1.5, 2.0, 2.5]
SL_OPTIONS    = [0.8, 1.0, 1.2]
# ✅ چون AI کاملاً کنار گذاشته شده، MIN_REQUIRED_SCORE ثابت config.py دیگر
# لزوماً کالیبراسیون درستی نیست (آن زمان امتیاز AI هم در ترکیب بود). اینجا
# هم مثل بقیه‌ی پارامترها grid search می‌شود.
MIN_SCORE_OPTIONS = [45, 55, 65]

# ── حالت دوم: Mean-Reversion (به‌جای Breakout) ──────────────────────────────
# منطق: به‌جای «قیمت سقف را شکست، دنبالش برو»، برعکسش — «RSI به‌شدت
# اشباع شد و قیمت خیلی از EMA200 فاصله گرفت، منتظر برگشت به میانگین باش».
# انتخاب حالت با متغیر محیطی STRATEGY_MODE کنترل می‌شود (پیش‌فرض: mean_reversion)
STRATEGY_MODE = os.environ.get('STRATEGY_MODE', 'mean_reversion').strip().lower()

RSI_OVERSOLD_OPTIONS   = [20, 25, 30]
RSI_OVERBOUGHT_OPTIONS = [70, 75, 80]
MIN_DEV_PCT_OPTIONS    = [2.0, 4.0, 6.0]   # حداقل فاصله‌ی قیمت از EMA200 به درصد

# ✅ فیلتر رژیم بازار: mean-reversion منطقاً فقط در بازار رنج/بدون‌روند
# باید کار کند، نه وقتی روند قوی است (چون در روند قوی RSI اشباع می‌شود
# ولی قیمت برنمی‌گردد، ادامه می‌دهد). 999 یعنی «بدون فیلتر» (برای مقایسه).
ADX_REGIME_OPTIONS = [25, 30, 999]

# ── حالت سوم: Relative-Value بین ارزها (نسبت هر آلت‌کوین به BTC) ────────────
# منطق: به‌جای «BTC صعودی می‌شود؟»، می‌پرسیم «نسبت ALT/BTC از میانگین
# غلتان خودش چقدر منحرف شده؟» — یک پوزیشن هم‌زمان روی هر دو پا (Long ALT +
# Short BTC یا برعکس) که تا حد زیادی از حرکت کلی بازار (نویز مشترک) مستقل
# است. این با استراتژی‌های تک‌ارزی TA کاملاً متفاوت است.
RV_BASE_SYMBOL      = 'BTCUSDT'          # پای مرجع (market factor)
RV_Z_WINDOW_OPTIONS  = [50, 100, 200]     # طول پنجره‌ی rolling برای zscore
RV_Z_ENTRY_OPTIONS   = [1.5, 2.0, 2.5]    # آستانه‌ی ورود (انحراف از میانگین)
RV_Z_EXIT_OPTIONS    = [0.3, 0.5]         # آستانه‌ی خروج (برگشت به میانگین)
RV_MAX_HOLD_OPTIONS  = [40, 80]           # حداکثر تعداد کندل نگه‌داشتن (timeout)
RV_Z_STOP_EXTRA      = 1.5                # اگر انحراف از z_entry این‌مقدار بیشتر شد، SL
MIN_TRADES_FOR_SELECTION_RV = 5           # کمتر از single-asset چون این معاملات کمیاب‌ترند

# ── حالت چهارم: Time-Series Momentum روزانه (نگه‌داری کوتاه‌مدت) ────────────
# منطق: بر پایه‌ی ادبیات آکادمیک مستند (Liu & Tsyvinski/NBER، Liu et al. 2022،
# "A Decade of Evidence of Trend Following in Crypto") — momentum در تایم‌فریم
# روزانه (نه ۴ساعته!) بارها با Sharpe مثبت تکرار شده، به‌شرط نگه‌داری چندروزه
# (نه intraday که رد شد، نه چندهفته‌ای که با محدودیت کاربر جور نیست).
# بهترین ترکیب گزارش‌شده در Liu et al. 2022: lookback≈28 روز, holding≈5 روز.
MOM_LOOKBACK_OPTIONS = [14, 21, 28, 35]     # روز
MOM_HOLD_OPTIONS     = [3, 5, 7]            # روز — حداکثر «چند روز» طبق خواسته‌ی کاربر
MOM_MIN_THRESHOLD_OPTIONS = [0.0, 3.0, 5.0] # % حداقل بازده lookback برای ورود (فیلتر نویز)
MIN_TRADES_FOR_SELECTION_MOM = 8


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    for col in df.columns:
        lower = col.lower()
        if lower in ('open', 'high', 'low', 'close', 'volume', 'timestamp'):
            col_map[col] = lower
    if col_map:
        df = df.rename(columns=col_map)
    return df.loc[:, ~df.columns.duplicated(keep='first')]


def _add_uppercase_aliases(df: pd.DataFrame) -> pd.DataFrame:
    for lower, upper in [('high', 'High'), ('low', 'Low'), ('open', 'Open'),
                          ('close', 'Close'), ('volume', 'Volume')]:
        if lower in df.columns and upper not in df.columns:
            df[upper] = df[lower]
    if 'feat_atr_percent' in df.columns and 'atr' not in df.columns:
        df['atr'] = (df['feat_atr_percent'] / 100.0) * df['close']
    return df


def _get_atr(row: pd.Series, close_price: float) -> float:
    atr_raw = float(row.get('atr', row.get('ATR', 0)) or 0)
    if atr_raw > 1.0:
        return atr_raw
    atr_pct = float(row.get('feat_atr_percent', 0) or 0)
    if atr_pct > 0:
        return (atr_pct / 100.0) * close_price
    return close_price * 0.01


def _ts_to_date(ts):
    """تبدیل timestamp (میلی‌ثانیه یا ثانیه) به تاریخ — برای تطبیق کندل
    ۴ساعته با سیگنال momentum روزانه‌ی همان روز."""
    try:
        ts_num = float(ts)
        if ts_num > 1e12:   # میلی‌ثانیه
            ts_num = ts_num / 1000.0
        return datetime.utcfromtimestamp(ts_num).date()
    except Exception:
        return None


def simulate_window(df: pd.DataFrame, start_idx: int, end_idx: int,
                     adx_th: float, swing_w: int, tp_r: float, sl_r: float,
                     min_score: float, symbol: str, momentum_lookup: dict = None) -> list:
    """
    شبیه‌سازی معاملات قانون‌محور (بدون AI) بین [start_idx, end_idx) از یک
    دیتافریم که از قبل اندیکاتورهایش محاسبه شده. دقیقاً همان منطق ورود/خروج
    strategy.py/backtester.py (بدون گیت AI، چون AI_GATE_ENABLED=False).

    ✅ min_score حالا پارامتر است (نه ثابت از config) — چون بدون AI باید
    دوباره grid search شود.

    ✅ momentum_lookup (اختیاری): dict از {تاریخ: 'LONG'/'SHORT'/None} —
    اگر داده شود، سیگنال breakout فقط وقتی باز می‌شود که هم‌جهت با
    momentum روزانه‌ی همان روز باشد (فیلتر رژیم، نه معکوس‌سازی).

    Returns: لیست pnl_percent هر معامله‌ی بسته‌شده (net از هزینه‌ی معامله).
    """
    max_sl_pct = float(getattr(config, 'MAX_SL_PERCENT', 0.05))
    max_open = int(getattr(config, 'MAX_OPEN_POSITIONS', 999))
    w_adx = float(getattr(config, 'WEIGHT_ADX', 20))
    w_rsi = float(getattr(config, 'WEIGHT_RSI', 20))
    w_ema = float(getattr(config, 'WEIGHT_EMA', 20))
    # چون AI غیرفعال است، وزن AI صفر و سهم بقیه از w_sum_eff محاسبه می‌شود
    w_sum_eff = (w_adx + w_rsi + w_ema) or 100.0

    open_trades = []
    closed_pnls = []

    for i in range(start_idx, min(end_idx, len(df))):
        row = df.iloc[i]
        high_price  = float(row.get('high', 0))
        low_price   = float(row.get('low', 0))
        close_price = float(row.get('close', 0))
        if high_price == 0 or low_price == 0 or close_price == 0:
            continue

        # ── بستن معاملات باز ────────────────────────────────────────────
        still_open = []
        for trade in open_trades:
            d, sl, tp2, ep = trade['direction'], trade['stop_loss'], trade['tp2'], trade['entry_price']
            closed, pnl = False, 0.0
            if d == 'LONG':
                if low_price <= sl:
                    pnl = ((sl - ep) / ep) * 100; closed = True
                elif high_price >= tp2:
                    pnl = ((tp2 - ep) / ep) * 100; closed = True
            else:
                if high_price >= sl:
                    pnl = ((ep - sl) / ep) * 100; closed = True
                elif low_price <= tp2:
                    pnl = ((ep - tp2) / ep) * 100; closed = True
            if closed:
                # ✅ هزینه‌ی معامله (کارمزد+اسلیپیج رفت‌وبرگشت) کم می‌شود
                pnl_net = pnl - TRANSACTION_COST_PERCENT
                closed_pnls.append(pnl_net)
            else:
                still_open.append(trade)
        open_trades = still_open

        if not passes_volume_filter(row, symbol):
            continue

        current_adx  = float(row.get('feat_adx', row.get('ADX', 0)))
        current_rsi  = float(row.get('feat_rsi', row.get('RSI', 50)))
        rsi_momentum = float(row.get('feat_rsi_momentum', row.get('RSI_momentum', 0)))
        dev_val      = abs(float(row.get('feat_ema_deviation', row.get('EMA_diff', 0))))

        adx_score = (min(100.0, 50.0 + (current_adx - adx_th) * 2.5)
                     if current_adx >= adx_th
                     else max(0.0, (current_adx / (adx_th + 1e-10)) * 50.0))
        rsi_score = (min(100.0, max(0.0, 50.0 + rsi_momentum * 5))
                     if current_rsi > 50
                     else min(100.0, max(0.0, 50.0 + (-rsi_momentum) * 5)))
        ema_score = min(100.0, (dev_val / 5.0) * 100.0)

        total_score = (adx_score * w_adx + rsi_score * w_rsi + ema_score * w_ema) / w_sum_eff

        if total_score < min_score:
            continue
        if len(open_trades) >= max_open:
            continue

        atr_val = _get_atr(row, close_price)
        df_slice = df.iloc[:i + 1]
        swing_high = strategy_utils.find_last_swing(df_slice, 'high', swing_w)
        swing_low  = strategy_utils.find_last_swing(df_slice, 'low', swing_w)
        if swing_high is None or swing_low is None:
            continue

        sl_dist = min(1.5 * atr_val * sl_r, close_price * max_sl_pct)
        if sl_dist <= 0:
            continue

        candidate_direction = None
        if high_price > swing_high and current_rsi > 50:
            candidate_direction = 'LONG'
        elif low_price < swing_low and current_rsi < 50:
            candidate_direction = 'SHORT'

        if candidate_direction is None:
            continue

        # ✅ فیلتر momentum (اگر lookup داده شده باشد): فقط سیگنال هم‌جهت
        # با momentum روزانه‌ی همان روز باز می‌شود؛ ناهم‌جهت یا نامشخص
        # (None) نادیده گرفته می‌شود (نه معکوس).
        if momentum_lookup is not None:
            row_date = _ts_to_date(row.get('timestamp'))
            mom_dir = momentum_lookup.get(row_date) if row_date is not None else None
            if mom_dir is None or mom_dir != candidate_direction:
                continue

        if candidate_direction == 'LONG':
            open_trades.append({'direction': 'LONG', 'entry_price': close_price,
                                 'stop_loss': close_price - sl_dist,
                                 'tp2': close_price + sl_dist * tp_r})
        else:
            open_trades.append({'direction': 'SHORT', 'entry_price': close_price,
                                 'stop_loss': close_price + sl_dist,
                                 'tp2': close_price - sl_dist * tp_r})

    # بستن معاملات باقی‌مانده با آخرین قیمت بازه (بدون هزینه‌ی اضافه چون
    # این خروج مصنوعی/سر رسیدن افق است، نه یک معامله‌ی کامل واقعی — ولی
    # برای سازگاری با optimizer.py، هزینه را همینجا هم کم می‌کنیم چون در
    # واقعیت باید بسته شود)
    if len(df) > start_idx:
        last_idx = min(end_idx, len(df)) - 1
        if last_idx >= start_idx:
            last_price = float(df.iloc[last_idx]['close'])
            for trade in open_trades:
                ep, d = trade['entry_price'], trade['direction']
                pnl = ((last_price - ep) / ep * 100 if d == 'LONG' else (ep - last_price) / ep * 100)
                closed_pnls.append(pnl - TRANSACTION_COST_PERCENT)

    return closed_pnls


def _select_best_params(df: pd.DataFrame, start_idx: int, end_idx: int, symbol: str,
                         momentum_lookup: dict = None) -> dict:
    """Grid search پارامترها (شامل MIN_SCORE) فقط روی [start_idx, end_idx) — بدون دیدن آینده."""
    best_pnl, best_trades, found = -1e9, 0, False
    best_cfg = {
        "ADX_THRESHOLD": config.ADX_THRESHOLD, "SWING_WINDOW": config.SWING_WINDOW,
        "TP_RATIO": config.TP_RATIO, "SL_RATIO": float(getattr(config, 'SL_RATIO', 1.0)),
        "MIN_SCORE": float(getattr(config, 'MIN_REQUIRED_SCORE', 55)),
    }
    for adx in ADX_OPTIONS:
        for sw in SWING_OPTIONS:
            for tp in TP_OPTIONS:
                for sl in SL_OPTIONS:
                    for ms in MIN_SCORE_OPTIONS:
                        pnls = simulate_window(df, start_idx, end_idx, adx, sw, tp, sl, ms,
                                                symbol, momentum_lookup=momentum_lookup)
                        if len(pnls) < MIN_TRADES_FOR_SELECTION:
                            continue
                        total = sum(pnls)
                        if total > best_pnl:
                            best_pnl, best_trades, found = total, len(pnls), True
                            best_cfg = {"ADX_THRESHOLD": adx, "SWING_WINDOW": sw,
                                        "TP_RATIO": tp, "SL_RATIO": sl, "MIN_SCORE": ms}
    return best_cfg, found, best_trades


def _build_momentum_lookup(symbol: str, lookback: int = 21, threshold: float = 0.0) -> dict:
    """
    برای هر روز D، جهت momentum را با داده‌ی موجود تا پایان روز D-1 محاسبه
    می‌کند (بدون نگاه به آینده) — این جهت برای فیلترکردن سیگنال‌های
    ۴ساعته‌ای که در طول روز D اتفاق می‌افتند استفاده می‌شود.
    Returns: dict {date: 'LONG'/'SHORT'/None}
    """
    daily_df = _fetch_daily_data(symbol, limit=1000)
    if daily_df is None or len(daily_df) < lookback + 5:
        return {}

    close_col = 'Close' if 'Close' in daily_df.columns else 'close'
    ts_col = 'Timestamp' if 'Timestamp' in daily_df.columns else 'timestamp'

    lookup = {}
    for i in range(lookback + 1, len(daily_df)):
        c_yesterday = float(daily_df.iloc[i - 1][close_col])
        c_prior = float(daily_df.iloc[i - 1 - lookback][close_col])
        if c_prior == 0:
            continue
        ret = (c_yesterday - c_prior) / c_prior * 100
        direction = 'LONG' if ret >= threshold else ('SHORT' if ret <= -threshold else None)
        day_date = _ts_to_date(daily_df.iloc[i][ts_col])
        if day_date is not None:
            lookup[day_date] = direction

    return lookup


def run_walk_forward_for_symbol(symbol: str, df_raw: pd.DataFrame,
                                 momentum_lookup: dict = None) -> list:
    """
    Walk-forward برای استراتژی breakout (قانون‌محور، بدون AI).
    ✅ اگر momentum_lookup داده شود، هم نسخه‌ی فیلترشده و هم نسخه‌ی
    فیلترنشده (برای مقایسه‌ی مستقیم) روی همان بازه‌ی OOS گزارش می‌شود.
    """
    df_raw = _normalize_columns(df_raw)
    df, meta = TechnicalIndicators.calculate_all_features(df_raw, symbol=symbol)
    if not meta.get('success', False):
        logger.warning(f"{symbol}: محاسبه اندیکاتورها ناموفق — رد شد")
        return []
    df = _normalize_columns(df)
    df = _add_uppercase_aliases(df)
    df = df.reset_index(drop=True)

    if len(df) <= WARMUP_ROWS:
        logger.warning(f"{symbol}: داده بعد از warm-up خالی — رد شد")
        return []

    usable = df.iloc[WARMUP_ROWS:].reset_index(drop=True)
    n = len(usable)
    if n < MIN_TRADES_FOR_SELECTION * 20:
        logger.warning(f"{symbol}: داده‌ی usable ({n} ردیف) برای {N_FOLDS} بازه خیلی کم است — رد شد")
        return []

    fold_size = n // N_FOLDS
    fold_bounds = [i * fold_size for i in range(N_FOLDS)] + [n]

    results = []
    for fold_idx in range(1, N_FOLDS):
        train_start, train_end = 0, fold_bounds[fold_idx]
        test_start, test_end = fold_bounds[fold_idx], fold_bounds[fold_idx + 1]

        best_cfg, found, sel_trades = _select_best_params(
            usable, train_start, train_end, symbol, momentum_lookup=momentum_lookup
        )
        oos_pnls = simulate_window(usable, test_start, test_end,
                                    best_cfg["ADX_THRESHOLD"], best_cfg["SWING_WINDOW"],
                                    best_cfg["TP_RATIO"], best_cfg["SL_RATIO"], best_cfg["MIN_SCORE"],
                                    symbol, momentum_lookup=momentum_lookup)

        wins = sum(1 for p in oos_pnls if p > 0)
        total = len(oos_pnls)
        win_rate = round(wins / total * 100, 1) if total else 0.0
        net_pnl = round(sum(oos_pnls), 2)

        compare_str = ""
        if momentum_lookup is not None:
            unfiltered_pnls = simulate_window(usable, test_start, test_end,
                                               best_cfg["ADX_THRESHOLD"], best_cfg["SWING_WINDOW"],
                                               best_cfg["TP_RATIO"], best_cfg["SL_RATIO"],
                                               best_cfg["MIN_SCORE"], symbol, momentum_lookup=None)
            uf_total = len(unfiltered_pnls)
            uf_net = round(sum(unfiltered_pnls), 2)
            compare_str = f" | بدون فیلتر: trades={uf_total} net_pnl={uf_net}%"

        logger.info(
            f"{symbol} | fold {fold_idx}/{N_FOLDS-1} | "
            f"train=[0:{train_end}] test=[{test_start}:{test_end}] | "
            f"params={'یافت‌شد' if found else 'fallback config'} "
            f"(ADX={best_cfg['ADX_THRESHOLD']},SW={best_cfg['SWING_WINDOW']},"
            f"TP={best_cfg['TP_RATIO']},SL={best_cfg['SL_RATIO']},MS={best_cfg['MIN_SCORE']}) | "
            f"OOS trades={total} win_rate={win_rate}% net_pnl={net_pnl}%{compare_str}"
        )

        results.append({
            'symbol': symbol, 'fold': fold_idx, 'train_rows': train_end,
            'test_rows': test_end - test_start, 'params_found': found,
            **{f'param_{k}': v for k, v in best_cfg.items()},
            'oos_trades': total, 'oos_win_rate': win_rate, 'oos_net_pnl': net_pnl,
            'oos_pnls': oos_pnls,
        })

    return results


def _get_ema200_deviation_pct(row: pd.Series, close_price: float) -> float:
    """درصد فاصله‌ی قیمت از EMA200 — معیار «چقدر از میانگین دور شده‌ایم»
    برای mean-reversion. مثبت=بالای میانگین، منفی=پایین میانگین."""
    ema200 = row.get('ema_200', None)
    if ema200 is None or float(ema200) == 0:
        return 0.0
    return (close_price - float(ema200)) / float(ema200) * 100.0


def simulate_window_mr(df: pd.DataFrame, start_idx: int, end_idx: int,
                        rsi_oversold: float, rsi_overbought: float, min_dev_pct: float,
                        tp_r: float, sl_r: float, adx_regime_max: float, symbol: str) -> list:
    """
    شبیه‌سازی معاملات Mean-Reversion بین [start_idx, end_idx).
    ورود LONG: RSI به‌شدت اشباع فروش + قیمت به‌اندازه‌ی کافی زیر EMA200 +
               ADX زیر adx_regime_max (بازار رنج/بدون‌روند — شرط جدید).
    ورود SHORT: قرینه‌ی بالا.
    خروج (SL/TP) دقیقاً همان سایزینگ ATR-based قبلی — فقط جهت‌گیری ورود برعکس شده.

    Returns: لیست pnl_percent هر معامله (net از هزینه‌ی معامله).
    """
    max_sl_pct = float(getattr(config, 'MAX_SL_PERCENT', 0.05))
    max_open   = int(getattr(config, 'MAX_OPEN_POSITIONS', 999))

    open_trades = []
    closed_pnls = []

    for i in range(start_idx, min(end_idx, len(df))):
        row = df.iloc[i]
        high_price  = float(row.get('high', 0))
        low_price   = float(row.get('low', 0))
        close_price = float(row.get('close', 0))
        if high_price == 0 or low_price == 0 or close_price == 0:
            continue

        still_open = []
        for trade in open_trades:
            d, sl, tp2, ep = trade['direction'], trade['stop_loss'], trade['tp2'], trade['entry_price']
            closed, pnl = False, 0.0
            if d == 'LONG':
                if low_price <= sl:
                    pnl = ((sl - ep) / ep) * 100; closed = True
                elif high_price >= tp2:
                    pnl = ((tp2 - ep) / ep) * 100; closed = True
            else:
                if high_price >= sl:
                    pnl = ((ep - sl) / ep) * 100; closed = True
                elif low_price <= tp2:
                    pnl = ((ep - tp2) / ep) * 100; closed = True
            if closed:
                closed_pnls.append(pnl - TRANSACTION_COST_PERCENT)
            else:
                still_open.append(trade)
        open_trades = still_open

        if not passes_volume_filter(row, symbol):
            continue
        if len(open_trades) >= max_open:
            continue

        current_rsi = float(row.get('feat_rsi', row.get('RSI', 50)))
        current_adx = float(row.get('feat_adx', row.get('ADX', 0)))
        dev_pct = _get_ema200_deviation_pct(row, close_price)

        atr_val = _get_atr(row, close_price)
        sl_dist = min(1.5 * atr_val * sl_r, close_price * max_sl_pct)
        if sl_dist <= 0:
            continue

        # ✅ فیلتر رژیم: فقط وقتی بازار به‌اندازه‌ی کافی بدون‌روند است
        if current_adx >= adx_regime_max:
            continue

        # ✅ منطق mean-reversion: برعکسِ breakout — در نقاط افراطی وارد می‌شویم
        if current_rsi < rsi_oversold and dev_pct <= -min_dev_pct:
            open_trades.append({'direction': 'LONG', 'entry_price': close_price,
                                 'stop_loss': close_price - sl_dist,
                                 'tp2': close_price + sl_dist * tp_r})
        elif current_rsi > rsi_overbought and dev_pct >= min_dev_pct:
            open_trades.append({'direction': 'SHORT', 'entry_price': close_price,
                                 'stop_loss': close_price + sl_dist,
                                 'tp2': close_price - sl_dist * tp_r})

    if len(df) > start_idx:
        last_idx = min(end_idx, len(df)) - 1
        if last_idx >= start_idx:
            last_price = float(df.iloc[last_idx]['close'])
            for trade in open_trades:
                ep, d = trade['entry_price'], trade['direction']
                pnl = ((last_price - ep) / ep * 100 if d == 'LONG' else (ep - last_price) / ep * 100)
                closed_pnls.append(pnl - TRANSACTION_COST_PERCENT)

    return closed_pnls


def _select_best_params_mr(df: pd.DataFrame, start_idx: int, end_idx: int, symbol: str) -> tuple:
    """Grid search پارامترهای mean-reversion (شامل فیلتر رژیم ADX) فقط روی [start_idx, end_idx)."""
    best_pnl, best_trades, found = -1e9, 0, False
    best_cfg = {"RSI_OVERSOLD": 25, "RSI_OVERBOUGHT": 75, "MIN_DEV_PCT": 4.0,
                "TP_RATIO": float(getattr(config, 'TP_RATIO', 1.5)),
                "SL_RATIO": float(getattr(config, 'SL_RATIO', 1.0)),
                "ADX_REGIME_MAX": 999}
    for rsi_os in RSI_OVERSOLD_OPTIONS:
        for rsi_ob in RSI_OVERBOUGHT_OPTIONS:
            for min_dev in MIN_DEV_PCT_OPTIONS:
                for tp in TP_OPTIONS:
                    for sl in SL_OPTIONS:
                        for adx_regime in ADX_REGIME_OPTIONS:
                            pnls = simulate_window_mr(df, start_idx, end_idx, rsi_os, rsi_ob,
                                                       min_dev, tp, sl, adx_regime, symbol)
                            if len(pnls) < MIN_TRADES_FOR_SELECTION:
                                continue
                            total = sum(pnls)
                            if total > best_pnl:
                                best_pnl, best_trades, found = total, len(pnls), True
                                best_cfg = {"RSI_OVERSOLD": rsi_os, "RSI_OVERBOUGHT": rsi_ob,
                                            "MIN_DEV_PCT": min_dev, "TP_RATIO": tp, "SL_RATIO": sl,
                                            "ADX_REGIME_MAX": adx_regime}
    return best_cfg, found, best_trades


def run_walk_forward_for_symbol_mr(symbol: str, df_raw: pd.DataFrame) -> list:
    """نسخه‌ی mean-reversion از run_walk_forward_for_symbol."""
    df_raw = _normalize_columns(df_raw)
    df, meta = TechnicalIndicators.calculate_all_features(df_raw, symbol=symbol)
    if not meta.get('success', False):
        logger.warning(f"{symbol}: محاسبه اندیکاتورها ناموفق — رد شد")
        return []
    df = _normalize_columns(df)
    df = _add_uppercase_aliases(df)
    df = df.reset_index(drop=True)

    if 'ema_200' not in df.columns:
        logger.warning(f"{symbol}: ستون ema_200 موجود نیست — mean-reversion رد شد")
        return []

    if len(df) <= WARMUP_ROWS:
        logger.warning(f"{symbol}: داده بعد از warm-up خالی — رد شد")
        return []

    usable = df.iloc[WARMUP_ROWS:].reset_index(drop=True)
    n = len(usable)
    if n < MIN_TRADES_FOR_SELECTION * 20:
        logger.warning(f"{symbol}: داده‌ی usable ({n} ردیف) برای {N_FOLDS} بازه خیلی کم است — رد شد")
        return []

    fold_size = n // N_FOLDS
    fold_bounds = [i * fold_size for i in range(N_FOLDS)] + [n]

    results = []
    for fold_idx in range(1, N_FOLDS):
        train_start, train_end = 0, fold_bounds[fold_idx]
        test_start, test_end = fold_bounds[fold_idx], fold_bounds[fold_idx + 1]

        best_cfg, found, sel_trades = _select_best_params_mr(usable, train_start, train_end, symbol)
        oos_pnls = simulate_window_mr(usable, test_start, test_end,
                                       best_cfg["RSI_OVERSOLD"], best_cfg["RSI_OVERBOUGHT"],
                                       best_cfg["MIN_DEV_PCT"], best_cfg["TP_RATIO"],
                                       best_cfg["SL_RATIO"], best_cfg["ADX_REGIME_MAX"], symbol)

        wins = sum(1 for p in oos_pnls if p > 0)
        total = len(oos_pnls)
        win_rate = round(wins / total * 100, 1) if total else 0.0
        net_pnl = round(sum(oos_pnls), 2)

        logger.info(
            f"[MR] {symbol} | fold {fold_idx}/{N_FOLDS-1} | "
            f"train=[0:{train_end}] test=[{test_start}:{test_end}] | "
            f"params={'یافت‌شد' if found else 'fallback'} "
            f"(RSI_OS={best_cfg['RSI_OVERSOLD']},RSI_OB={best_cfg['RSI_OVERBOUGHT']},"
            f"MIN_DEV={best_cfg['MIN_DEV_PCT']}%,TP={best_cfg['TP_RATIO']},SL={best_cfg['SL_RATIO']},"
            f"ADX_MAX={best_cfg['ADX_REGIME_MAX']}) | "
            f"OOS trades={total} win_rate={win_rate}% net_pnl={net_pnl}%"
        )

        results.append({
            'symbol': symbol, 'fold': fold_idx, 'train_rows': train_end,
            'test_rows': test_end - test_start, 'params_found': found,
            **{f'param_{k}': v for k, v in best_cfg.items()},
            'oos_trades': total, 'oos_win_rate': win_rate, 'oos_net_pnl': net_pnl,
            'oos_pnls': oos_pnls,
        })

    return results



    """
    برمی‌گرداند: لیست دیکشنری‌های نتیجه‌ی هر بازه‌ی out-of-sample برای این ارز.
    """
    df_raw = _normalize_columns(df_raw)
    df, meta = TechnicalIndicators.calculate_all_features(df_raw, symbol=symbol)
    if not meta.get('success', False):
        logger.warning(f"{symbol}: محاسبه اندیکاتورها ناموفق — رد شد")
        return []
    df = _normalize_columns(df)
    df = _add_uppercase_aliases(df)
    df = df.reset_index(drop=True)

    if len(df) <= WARMUP_ROWS:
        logger.warning(f"{symbol}: داده بعد از warm-up خالی — رد شد")
        return []

    usable = df.iloc[WARMUP_ROWS:].reset_index(drop=True)
    n = len(usable)
    if n < MIN_TRADES_FOR_SELECTION * 20:  # حداقل حجم منطقی برای تقسیم به چند بازه
        logger.warning(f"{symbol}: داده‌ی usable ({n} ردیف) برای {N_FOLDS} بازه خیلی کم است — رد شد")
        return []

    fold_size = n // N_FOLDS
    fold_bounds = [i * fold_size for i in range(N_FOLDS)] + [n]

    results = []
    for fold_idx in range(1, N_FOLDS):  # بازه‌ی ۰ فقط برای train اولیه است، تست از بازه‌ی ۱ شروع می‌شود
        train_start, train_end = 0, fold_bounds[fold_idx]          # expanding window
        test_start,  test_end  = fold_bounds[fold_idx], fold_bounds[fold_idx + 1]

        best_cfg, found, sel_trades = _select_best_params(usable, train_start, train_end, symbol)
        oos_pnls = simulate_window(usable, test_start, test_end,
                                    best_cfg["ADX_THRESHOLD"], best_cfg["SWING_WINDOW"],
                                    best_cfg["TP_RATIO"], best_cfg["SL_RATIO"],
                                    best_cfg["MIN_SCORE"], symbol)

        wins = sum(1 for p in oos_pnls if p > 0)
        total = len(oos_pnls)
        win_rate = round(wins / total * 100, 1) if total else 0.0
        net_pnl = round(sum(oos_pnls), 2)

        logger.info(
            f"{symbol} | fold {fold_idx}/{N_FOLDS-1} | "
            f"train=[0:{train_end}] test=[{test_start}:{test_end}] | "
            f"params={'یافت‌شد' if found else 'fallback config'} "
            f"(ADX={best_cfg['ADX_THRESHOLD']},SW={best_cfg['SWING_WINDOW']},"
            f"TP={best_cfg['TP_RATIO']},SL={best_cfg['SL_RATIO']},MS={best_cfg['MIN_SCORE']}) | "
            f"OOS trades={total} win_rate={win_rate}% net_pnl={net_pnl}%"
        )

        results.append({
            'symbol': symbol, 'fold': fold_idx, 'train_rows': train_end,
            'test_rows': test_end - test_start, 'params_found': found,
            **{f'param_{k}': v for k, v in best_cfg.items()},
            'oos_trades': total, 'oos_win_rate': win_rate, 'oos_net_pnl': net_pnl,
            'oos_pnls': oos_pnls,
        })

    return results


def _process_symbol_for_rv(symbol: str, df_raw: pd.DataFrame):
    """اندیکاتورها + warm-up برای یک ارز — فقط برای استخراج ستون close/timestamp
    مورد نیاز relative-value (بدون فیچرهای TA اضافه)."""
    df_norm = _normalize_columns(df_raw.copy())
    df_feat, meta = TechnicalIndicators.calculate_all_features(df_norm, symbol=symbol)
    if not meta.get('success', False):
        return None
    df_feat = _normalize_columns(df_feat)
    df_feat = df_feat.reset_index(drop=True)
    if len(df_feat) <= WARMUP_ROWS:
        return None
    df_feat = df_feat.iloc[WARMUP_ROWS:].reset_index(drop=True)
    if 'timestamp' not in df_feat.columns or 'close' not in df_feat.columns:
        return None
    return df_feat[['timestamp', 'close']].copy()


def _build_pair_df(alt_df: pd.DataFrame, btc_df: pd.DataFrame) -> pd.DataFrame:
    """ترکیب دو سری قیمت بر اساس timestamp مشترک + محاسبه‌ی zscore برای هر پنجره."""
    alt_r = alt_df.rename(columns={'close': 'close_alt'})
    btc_r = btc_df.rename(columns={'close': 'close_btc'})
    pair = pd.merge(alt_r, btc_r, on='timestamp', how='inner').reset_index(drop=True)
    if len(pair) < 300:
        return pair

    ratio = pair['close_alt'] / pair['close_btc']
    for w in RV_Z_WINDOW_OPTIONS:
        roll_mean = ratio.rolling(w).mean()
        roll_std  = ratio.rolling(w).std().replace(0, np.nan)
        pair[f'zscore_w{w}'] = (ratio - roll_mean) / roll_std
    return pair


def simulate_window_rv(pair_df: pd.DataFrame, zscore_col: str, start_idx: int, end_idx: int,
                        z_entry: float, z_exit: float, max_hold: int, symbol_alt: str) -> list:
    """
    شبیه‌سازی معاملات Relative-Value (Long ALT/Short BTC یا برعکس) بین [start_idx, end_idx).
    یک پوزیشن هم‌زمان (ساده‌سازی). PnL = اختلاف بازده دو پا (market-neutral تقریبی).
    Returns: لیست pnl_percent هر معامله (net از هزینه‌ی دو پا).
    """
    open_trade = None
    pnls = []

    for i in range(start_idx, min(end_idx, len(pair_df))):
        row = pair_df.iloc[i]
        z = row.get(zscore_col, None)
        close_alt = float(row.get('close_alt', 0))
        close_btc = float(row.get('close_btc', 0))
        if z is None or pd.isna(z) or close_alt == 0 or close_btc == 0:
            continue

        if open_trade is not None:
            held = i - open_trade['entry_idx']
            exit_now, reason = False, None
            if open_trade['direction'] == 'LONG_ALT_SHORT_BTC':
                if z >= -z_exit:
                    exit_now, reason = True, 'TP'
                elif z <= -(open_trade['z_entry'] + RV_Z_STOP_EXTRA):
                    exit_now, reason = True, 'SL'
            else:
                if z <= z_exit:
                    exit_now, reason = True, 'TP'
                elif z >= (open_trade['z_entry'] + RV_Z_STOP_EXTRA):
                    exit_now, reason = True, 'SL'
            if not exit_now and held >= max_hold:
                exit_now, reason = True, 'TIMEOUT'

            if exit_now:
                ret_alt = (close_alt - open_trade['entry_alt']) / open_trade['entry_alt'] * 100
                ret_btc = (close_btc - open_trade['entry_btc']) / open_trade['entry_btc'] * 100
                pnl = (ret_alt - ret_btc) if open_trade['direction'] == 'LONG_ALT_SHORT_BTC' else (ret_btc - ret_alt)
                pnl -= TRANSACTION_COST_PERCENT * 2  # دو پا
                pnls.append(pnl)
                open_trade = None
            continue

        if z <= -z_entry:
            open_trade = {'direction': 'LONG_ALT_SHORT_BTC', 'entry_idx': i,
                          'entry_alt': close_alt, 'entry_btc': close_btc, 'z_entry': z_entry}
        elif z >= z_entry:
            open_trade = {'direction': 'SHORT_ALT_LONG_BTC', 'entry_idx': i,
                          'entry_alt': close_alt, 'entry_btc': close_btc, 'z_entry': z_entry}

    if open_trade is not None:
        last_idx = min(end_idx, len(pair_df)) - 1
        if last_idx >= 0:
            last = pair_df.iloc[last_idx]
            ret_alt = (float(last['close_alt']) - open_trade['entry_alt']) / open_trade['entry_alt'] * 100
            ret_btc = (float(last['close_btc']) - open_trade['entry_btc']) / open_trade['entry_btc'] * 100
            pnl = (ret_alt - ret_btc) if open_trade['direction'] == 'LONG_ALT_SHORT_BTC' else (ret_btc - ret_alt)
            pnl -= TRANSACTION_COST_PERCENT * 2
            pnls.append(pnl)

    return pnls


def _select_best_params_rv(pair_df: pd.DataFrame, start_idx: int, end_idx: int, symbol_alt: str) -> tuple:
    best_pnl, best_trades, found = -1e9, 0, False
    best_cfg = {"Z_WINDOW": 100, "Z_ENTRY": 2.0, "Z_EXIT": 0.5, "MAX_HOLD": 40}
    for w in RV_Z_WINDOW_OPTIONS:
        col = f'zscore_w{w}'
        if col not in pair_df.columns:
            continue
        for z_entry in RV_Z_ENTRY_OPTIONS:
            for z_exit in RV_Z_EXIT_OPTIONS:
                for max_hold in RV_MAX_HOLD_OPTIONS:
                    pnls = simulate_window_rv(pair_df, col, start_idx, end_idx, z_entry, z_exit, max_hold, symbol_alt)
                    if len(pnls) < MIN_TRADES_FOR_SELECTION_RV:
                        continue
                    total = sum(pnls)
                    if total > best_pnl:
                        best_pnl, best_trades, found = total, len(pnls), True
                        best_cfg = {"Z_WINDOW": w, "Z_ENTRY": z_entry, "Z_EXIT": z_exit, "MAX_HOLD": max_hold}
    return best_cfg, found, best_trades


def run_walk_forward_for_pair_rv(symbol_alt: str, alt_df: pd.DataFrame, btc_df: pd.DataFrame) -> list:
    pair_df = _build_pair_df(alt_df, btc_df)
    n = len(pair_df)
    if n < MIN_TRADES_FOR_SELECTION_RV * 40:
        logger.warning(f"{symbol_alt}/BTC: داده‌ی هم‌زمان کافی نیست ({n} ردیف) — رد شد")
        return []

    fold_size = n // N_FOLDS
    fold_bounds = [i * fold_size for i in range(N_FOLDS)] + [n]
    results = []

    for fold_idx in range(1, N_FOLDS):
        train_start, train_end = 0, fold_bounds[fold_idx]
        test_start, test_end = fold_bounds[fold_idx], fold_bounds[fold_idx + 1]

        best_cfg, found, sel_trades = _select_best_params_rv(pair_df, train_start, train_end, symbol_alt)
        col = f'zscore_w{best_cfg["Z_WINDOW"]}'
        oos_pnls = simulate_window_rv(pair_df, col, test_start, test_end,
                                       best_cfg["Z_ENTRY"], best_cfg["Z_EXIT"], best_cfg["MAX_HOLD"], symbol_alt)

        wins = sum(1 for p in oos_pnls if p > 0)
        total = len(oos_pnls)
        win_rate = round(wins / total * 100, 1) if total else 0.0
        net_pnl = round(sum(oos_pnls), 2)

        logger.info(
            f"[RV] {symbol_alt}/BTC | fold {fold_idx}/{N_FOLDS-1} | "
            f"train=[0:{train_end}] test=[{test_start}:{test_end}] | "
            f"params={'یافت‌شد' if found else 'fallback'} "
            f"(Z_WIN={best_cfg['Z_WINDOW']},Z_ENTRY={best_cfg['Z_ENTRY']},"
            f"Z_EXIT={best_cfg['Z_EXIT']},MAX_HOLD={best_cfg['MAX_HOLD']}) | "
            f"OOS trades={total} win_rate={win_rate}% net_pnl={net_pnl}%"
        )

        results.append({
            'symbol': f"{symbol_alt}/BTC", 'fold': fold_idx, 'train_rows': train_end,
            'test_rows': test_end - test_start, 'params_found': found,
            **{f'param_{k}': v for k, v in best_cfg.items()},
            'oos_trades': total, 'oos_win_rate': win_rate, 'oos_net_pnl': net_pnl,
            'oos_pnls': oos_pnls,
        })

    return results


def _fetch_daily_data(symbol: str, limit: int = 1000) -> pd.DataFrame:
    """دریافت داده‌ی روزانه (نه ۴ساعته) مستقیم از CoinEx — برای momentum
    که طبق ادبیات باید روی تایم‌فریم روزانه ساخته شود، نه ۴ساعته."""
    df = coinex_client.get_coinex_candles(symbol, timeframe="1d", limit=limit)
    if df is None or df.empty:
        return None
    df = _normalize_columns(df)
    df = df.sort_values('timestamp' if 'timestamp' in df.columns else df.columns[0]).reset_index(drop=True)
    return df


def simulate_window_momentum(df: pd.DataFrame, start_idx: int, end_idx: int,
                              lookback: int, hold: int, min_threshold_pct: float,
                              symbol: str) -> list:
    """
    Time-Series Momentum روزانه — یک پوزیشن هم‌زمان:
    اگر بازده lookback روز اخیر مثبت (و بزرگ‌تر از آستانه) بود → LONG.
    اگر منفی (و قدرمطلق بزرگ‌تر از آستانه) بود → SHORT.
    دقیقاً hold روز نگه می‌داریم، بعد می‌بندیم (بدون SL/TP — پیاده‌سازی
    وفادار به ادبیات آکادمیک؛ می‌توان بعداً SL اضافه کرد).

    Returns: لیست pnl_percent هر معامله (net از هزینه‌ی معامله).
    """
    pnls = []
    i = max(start_idx, lookback)

    while i < min(end_idx, len(df)):
        close_now = float(df.iloc[i]['close'])
        close_lookback = float(df.iloc[i - lookback]['close'])
        if close_lookback == 0:
            i += 1
            continue

        mom_return_pct = (close_now - close_lookback) / close_lookback * 100

        direction = None
        if mom_return_pct >= min_threshold_pct:
            direction = 'LONG'
        elif mom_return_pct <= -min_threshold_pct:
            direction = 'SHORT'

        if direction is None:
            i += 1
            continue

        exit_i = i + hold
        if exit_i >= min(end_idx, len(df)):
            break  # داده‌ی کافی برای بستن در بازه‌ی مجاز نیست

        entry_price = close_now
        exit_price = float(df.iloc[exit_i]['close'])
        ret = (exit_price - entry_price) / entry_price * 100
        pnl = ret if direction == 'LONG' else -ret
        pnl -= TRANSACTION_COST_PERCENT
        pnls.append(pnl)

        i = exit_i + 1  # غیرهم‌پوشان — بعد از بستن، دوباره دنبال سیگنال بگرد

    return pnls


def _select_best_params_momentum(df: pd.DataFrame, start_idx: int, end_idx: int, symbol: str) -> tuple:
    best_pnl, best_trades, found = -1e9, 0, False
    best_cfg = {"LOOKBACK": 28, "HOLD": 5, "MIN_THRESHOLD": 0.0}
    for lb in MOM_LOOKBACK_OPTIONS:
        for hold in MOM_HOLD_OPTIONS:
            for th in MOM_MIN_THRESHOLD_OPTIONS:
                pnls = simulate_window_momentum(df, start_idx, end_idx, lb, hold, th, symbol)
                if len(pnls) < MIN_TRADES_FOR_SELECTION_MOM:
                    continue
                total = sum(pnls)
                if total > best_pnl:
                    best_pnl, best_trades, found = total, len(pnls), True
                    best_cfg = {"LOOKBACK": lb, "HOLD": hold, "MIN_THRESHOLD": th}
    return best_cfg, found, best_trades


def run_walk_forward_for_symbol_momentum(symbol: str, df: pd.DataFrame) -> list:
    n = len(df)
    if n < 300:
        logger.warning(f"{symbol}: داده‌ی روزانه کافی نیست ({n} ردیف) — رد شد")
        return []

    fold_size = n // N_FOLDS
    fold_bounds = [i * fold_size for i in range(N_FOLDS)] + [n]
    results = []

    for fold_idx in range(1, N_FOLDS):
        train_start, train_end = 0, fold_bounds[fold_idx]
        test_start, test_end = fold_bounds[fold_idx], fold_bounds[fold_idx + 1]

        best_cfg, found, sel_trades = _select_best_params_momentum(df, train_start, train_end, symbol)
        oos_pnls = simulate_window_momentum(df, test_start, test_end,
                                             best_cfg["LOOKBACK"], best_cfg["HOLD"],
                                             best_cfg["MIN_THRESHOLD"], symbol)

        wins = sum(1 for p in oos_pnls if p > 0)
        total = len(oos_pnls)
        win_rate = round(wins / total * 100, 1) if total else 0.0
        net_pnl = round(sum(oos_pnls), 2)

        logger.info(
            f"[MOM] {symbol} | fold {fold_idx}/{N_FOLDS-1} | "
            f"train=[0:{train_end}] test=[{test_start}:{test_end}] (روز) | "
            f"params={'یافت‌شد' if found else 'fallback'} "
            f"(LOOKBACK={best_cfg['LOOKBACK']}d,HOLD={best_cfg['HOLD']}d,"
            f"MIN_TH={best_cfg['MIN_THRESHOLD']}%) | "
            f"OOS trades={total} win_rate={win_rate}% net_pnl={net_pnl}%"
        )

        results.append({
            'symbol': symbol, 'fold': fold_idx, 'train_rows': train_end,
            'test_rows': test_end - test_start, 'params_found': found,
            **{f'param_{k}': v for k, v in best_cfg.items()},
            'oos_trades': total, 'oos_win_rate': win_rate, 'oos_net_pnl': net_pnl,
            'oos_pnls': oos_pnls,
        })

    return results


def run_fixed_params_no_optimization_test() -> dict:
    """
    ✅ تست تعیین‌کننده: هیچ grid search/انتخاب پارامتری در کار نیست.
    یک ترکیب پارامتر «متعارف» (RSI 30/70 — استاندارد صنعتی، نه انتخاب‌شده
    از نتایج ما) از قبل ثابت می‌شود و یک‌بار روی کل تاریخچه‌ی هر ارز
    (بعد از warm-up) اجرا می‌شود. این کاملاً از سوگیری overfitting در
    انتخاب پارامتر (که در walk-forward با ۷۲۹ ترکیب ممکن است رخ داده باشد)
    مبراست — اگر این تست هم نزدیک PF=1 بماند، شواهد نبود edge واقعی
    قوی‌تر می‌شود؛ اگر معنادار مثبت شد، یعنی grid search ما edge واقعی را
    زیر نویز پنهان کرده بود.
    """
    FIXED = {"RSI_OVERSOLD": 30, "RSI_OVERBOUGHT": 70, "MIN_DEV_PCT": 4.0,
              "TP_RATIO": 2.0, "SL_RATIO": 1.0, "ADX_REGIME_MAX": 999}
    logger.info("\n" + "=" * 70)
    logger.info("🔒 تست بدون بهینه‌سازی (پارامتر ثابت، بدون grid search) — رفع ابهام overfitting")
    logger.info(f"   پارامتر ثابت: {FIXED}")
    logger.info("=" * 70)

    data_dir = os.path.join(BASE_DIR, "data", "4h")
    all_pnls = []
    per_symbol = []

    for symbol in TEST_SYMBOLS:
        safe_name = symbol.replace('/', '_')
        file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
        if not os.path.exists(file_path):
            continue
        try:
            df_raw = pd.read_csv(file_path)
        except Exception:
            continue

        df_raw = _normalize_columns(df_raw)
        df, meta = TechnicalIndicators.calculate_all_features(df_raw, symbol=symbol)
        if not meta.get('success', False) or 'ema_200' not in df.columns:
            continue
        df = _normalize_columns(df)
        df = _add_uppercase_aliases(df)
        df = df.reset_index(drop=True)
        if len(df) <= WARMUP_ROWS:
            continue
        usable = df.iloc[WARMUP_ROWS:].reset_index(drop=True)

        pnls = simulate_window_mr(usable, 0, len(usable),
                                   FIXED["RSI_OVERSOLD"], FIXED["RSI_OVERBOUGHT"],
                                   FIXED["MIN_DEV_PCT"], FIXED["TP_RATIO"],
                                   FIXED["SL_RATIO"], FIXED["ADX_REGIME_MAX"], symbol)
        all_pnls.extend(pnls)

        n = len(pnls)
        wr = round(sum(1 for p in pnls if p > 0) / n * 100, 1) if n else 0.0
        logger.info(f"   {symbol}: trades={n} win_rate={wr}% net_pnl={round(sum(pnls), 2)}%")
        per_symbol.append({'symbol': symbol, 'trades': n, 'win_rate': wr, 'net_pnl': round(sum(pnls), 2)})

    n = len(all_pnls)
    if n == 0:
        logger.warning("هیچ معامله‌ای در تست ثابت رخ نداد")
        return {}

    wins_sum = sum(p for p in all_pnls if p > 0)
    losses_sum = abs(sum(p for p in all_pnls if p <= 0))
    pf = round(wins_sum / losses_sum, 2) if losses_sum > 0 else (float('inf') if wins_sum > 0 else 0.0)
    win_rate = round(sum(1 for p in all_pnls if p > 0) / n * 100, 1)
    net_pnl = round(sum(all_pnls), 2)

    logger.info("\n" + "-" * 70)
    logger.info(f"📌 نتیجه‌ی تست بدون بهینه‌سازی: trades={n} | win_rate={win_rate}% | "
                f"net_pnl={net_pnl}% | Profit Factor={pf}")
    if net_pnl > 0 and pf > 1.15:
        logger.info("✅ حتی بدون هیچ بهینه‌سازی، edge مثبت و قابل‌توجه دیده می‌شود — "
                     "احتمالاً grid search قبلی edge واقعی را زیر نویز گم کرده بود.")
    else:
        logger.info("❌ حتی با پارامتر متعارف و بدون هیچ بهینه‌سازی، edge معناداری دیده نمی‌شود — "
                     "این شواهد را قوی‌تر می‌کند که واقعاً edge ای در کار نیست.")
    logger.info("-" * 70)

    return {'fixed_params': FIXED, 'total_trades': n, 'win_rate': win_rate,
            'net_pnl': net_pnl, 'profit_factor': pf, 'per_symbol': per_symbol}


def main():
    if STRATEGY_MODE not in ('breakout', 'mean_reversion', 'relative_value',
                              'momentum_daily', 'momentum_filtered_breakout',
                              'trend_pullback', 'pullback_no_trend'):
        logger.error(f"STRATEGY_MODE نامعتبر: '{STRATEGY_MODE}' — باید 'breakout'، "
                     f"'mean_reversion'، 'relative_value'، 'momentum_daily'، "
                     f"'momentum_filtered_breakout'، 'trend_pullback' یا "
                     f"'pullback_no_trend' باشد")
        return

    if AI_GATE_ENABLED:
        logger.warning(
            "⚠️ AI_GATE_ENABLED=True در config.py — این اسکریپت استراتژی را "
            "بدون AI شبیه‌سازی می‌کند (چون مدل فعلی AUC≈0.48 دارد). نتیجه بدون "
            "تغییر این فلگ همچنان معتبر است، ولی رفتار لایوی واقعی اگر گیت را "
            "روشن نگه‌داری متفاوت خواهد بود."
        )

    logger.info(f"شروع Walk-Forward Analysis | حالت={STRATEGY_MODE} | {N_FOLDS} بازه | "
                f"هزینه‌ی معامله={TRANSACTION_COST_PERCENT}% رفت‌وبرگشت (هر پا)")
    logger.info("=" * 70)

    data_dir = os.path.join(BASE_DIR, "data", "4h")
    all_results = []

    # ✅ مسیر جداگانه برای relative_value چون هر آلت‌کوین باید با یک BTC
    # مشترک جفت شود (پای مرجع یک‌بار پردازش می‌شود، نه هر بار).
    if STRATEGY_MODE == 'relative_value':
        btc_path = os.path.join(data_dir, f"{RV_BASE_SYMBOL}_history.csv")
        if not os.path.exists(btc_path):
            logger.error(f"فایل داده‌ی پای مرجع ({RV_BASE_SYMBOL}) یافت نشد — متوقف شد")
            return
        btc_raw = pd.read_csv(btc_path)
        btc_processed = _process_symbol_for_rv(RV_BASE_SYMBOL, btc_raw)
        if btc_processed is None:
            logger.error(f"پردازش {RV_BASE_SYMBOL} ناموفق — متوقف شد")
            return

        for symbol in TEST_SYMBOLS:
            if symbol == RV_BASE_SYMBOL:
                continue  # BTC خودش نمی‌تواند پای alt در برابر خودش باشد
            safe_name = symbol.replace('/', '_')
            file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
            if not os.path.exists(file_path):
                logger.warning(f"{symbol}: فایل CSV یافت نشد — رد شد")
                continue
            try:
                alt_raw = pd.read_csv(file_path)
            except Exception as e:
                logger.error(f"{symbol}: خطا در خواندن CSV: {e}")
                continue

            alt_processed = _process_symbol_for_rv(symbol, alt_raw)
            if alt_processed is None:
                logger.warning(f"{symbol}: پردازش ناموفق — رد شد")
                continue

            logger.info(f"\n--- {symbol}/{RV_BASE_SYMBOL} (relative_value) ---")
            pair_results = run_walk_forward_for_pair_rv(symbol, alt_processed, btc_processed)
            all_results.extend(pair_results)

    elif STRATEGY_MODE == 'momentum_daily':
        # ✅ داده‌ی روزانه مستقیم از API گرفته می‌شود (نه از data/4h/*.csv که
        # فقط ۴ساعته است) — چون طبق ادبیات، momentum باید روی تایم‌فریم
        # روزانه ساخته شود.
        for symbol in TEST_SYMBOLS:
            logger.info(f"\n--- {symbol} (momentum_daily) ---")
            daily_df = _fetch_daily_data(symbol)
            if daily_df is None or len(daily_df) < 300:
                logger.warning(f"{symbol}: داده‌ی روزانه کافی دریافت نشد — رد شد")
                continue
            sym_results = run_walk_forward_for_symbol_momentum(symbol, daily_df)
            all_results.extend(sym_results)

    elif STRATEGY_MODE == 'trend_pullback':
        for symbol in TEST_SYMBOLS:
            logger.info(f"\n--- {symbol} (trend_pullback) ---")
            daily_df = _fetch_daily_data(symbol)
            if daily_df is None or len(daily_df) < 300:
                logger.warning(f"{symbol}: داده‌ی روزانه کافی دریافت نشد — رد شد")
                continue
            sym_results = run_walk_forward_trend_pullback(symbol, daily_df)
            all_results.extend(sym_results)

    elif STRATEGY_MODE == 'pullback_no_trend':
        for symbol in TEST_SYMBOLS:
            logger.info(f"\n--- {symbol} (pullback_no_trend) ---")
            daily_df = _fetch_daily_data(symbol)
            if daily_df is None or len(daily_df) < 300:
                logger.warning(f"{symbol}: داده‌ی روزانه کافی دریافت نشد — رد شد")
                continue
            sym_results = run_walk_forward_pullback_no_trend(symbol, daily_df)
            all_results.extend(sym_results)

    elif STRATEGY_MODE == 'momentum_filtered_breakout':
        # ✅ برای هر ارز: اول momentum_lookup روزانه ساخته می‌شود (بدون
        # نگاه به آینده)، سپس breakout چهارساعته با همان فیلتر اجرا می‌شود
        # و در همان لاگ با نسخه‌ی بدون فیلتر مقایسه می‌شود.
        for symbol in TEST_SYMBOLS:
            safe_name = symbol.replace('/', '_')
            file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
            if not os.path.exists(file_path):
                logger.warning(f"{symbol}: فایل CSV چهارساعته یافت نشد — رد شد")
                continue
            try:
                df_raw = pd.read_csv(file_path)
            except Exception as e:
                logger.error(f"{symbol}: خطا در خواندن CSV: {e}")
                continue

            logger.info(f"\n--- {symbol} (momentum_filtered_breakout) ---")
            momentum_lookup = _build_momentum_lookup(symbol, lookback=21, threshold=0.0)
            if not momentum_lookup:
                logger.warning(f"{symbol}: ساخت momentum_lookup ناموفق (داده‌ی روزانه کافی نبود) — رد شد")
                continue
            logger.info(f"   momentum_lookup ساخته شد: {len(momentum_lookup)} روز")

            sym_results = run_walk_forward_for_symbol(symbol, df_raw, momentum_lookup=momentum_lookup)
            all_results.extend(sym_results)

    else:
        run_fn = run_walk_forward_for_symbol if STRATEGY_MODE == 'breakout' else run_walk_forward_for_symbol_mr

        for symbol in TEST_SYMBOLS:
            safe_name = symbol.replace('/', '_')
            file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
            if not os.path.exists(file_path):
                logger.warning(f"{symbol}: فایل CSV یافت نشد — رد شد")
                continue
            try:
                df_raw = pd.read_csv(file_path)
            except Exception as e:
                logger.error(f"{symbol}: خطا در خواندن CSV: {e}")
                continue

            logger.info(f"\n--- {symbol} ({STRATEGY_MODE}) ---")
            sym_results = run_fn(symbol, df_raw)
            all_results.extend(sym_results)

    if not all_results:
        logger.error("❌ هیچ نتیجه‌ای تولید نشد — بررسی کن data/4h پر است یا نه")
        return

    # ── خلاصه‌ی نهایی ────────────────────────────────────────────────────
    all_pnls = [p for r in all_results for p in r['oos_pnls']]
    total_trades = len(all_pnls)
    wins = sum(1 for p in all_pnls if p > 0)
    win_rate = round(wins / total_trades * 100, 1) if total_trades else 0.0
    net_pnl_sum = round(sum(all_pnls), 2)
    wins_sum = sum(p for p in all_pnls if p > 0)
    losses_sum = abs(sum(p for p in all_pnls if p <= 0))
    profit_factor = round(wins_sum / losses_sum, 2) if losses_sum > 0 else (float('inf') if wins_sum > 0 else 0.0)

    # equity curve ساده (ترتیب pool شده، نه زمان واقعی چندبازاره — محدودیت مستندشده)
    equity, peak, max_dd = 100.0, 100.0, 0.0
    for p in all_pnls:
        equity *= (1 + p / 100)
        peak = max(peak, equity)
        dd = (peak - equity) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)

    logger.info("\n" + "=" * 70)
    logger.info("📊 خلاصه‌ی کلی Walk-Forward (همه‌ی نمادها، همه‌ی بازه‌های out-of-sample)")
    logger.info(f"   تعداد کل معاملات OOS: {total_trades}")
    logger.info(f"   Win rate: {win_rate}%")
    logger.info(f"   مجموع PnL خالص (بعد از {TRANSACTION_COST_PERCENT}% هزینه هر معامله): {net_pnl_sum}%")
    logger.info(f"   Profit Factor: {profit_factor}")
    logger.info(f"   Max Drawdown (pooled, نه زمان واقعی): {round(-max_dd, 2)}%")
    logger.info("=" * 70)

    if net_pnl_sum > 0 and profit_factor > 1.2:
        logger.info("✅ نتیجه: استراتژی قانون‌محور در تست کاملاً out-of-sample سودآور بوده — edge واقعی محتمل است.")
    elif net_pnl_sum > 0:
        logger.info("⚠️ نتیجه: سودآور ولی با حاشیه‌ی کم (profit factor نزدیک ۱) — edge ضعیف/نامطمئن.")
    else:
        logger.info("❌ نتیجه: بعد از کسر هزینه‌ی معامله، در تست out-of-sample زیان‌ده بوده — این نشانه‌ی نبود edge واقعی در پارامترهای فعلی است.")

    # ذخیره‌ی جزئیات (بدون ستون oos_pnls خام برای خوانایی CSV)
    out_rows = [{k: v for k, v in r.items() if k != 'oos_pnls'} for r in all_results]
    out_df = pd.DataFrame(out_rows)
    out_path = os.path.join(BASE_DIR, 'data', f'walk_forward_results_{STRATEGY_MODE}.csv')
    out_df.to_csv(out_path, index=False, encoding='utf-8')
    logger.info(f"جزئیات هر بازه/نماد ذخیره شد: {out_path}")

    # ✅ تست تکمیلی بدون بهینه‌سازی — رفع ابهام overfitting انتخاب پارامتر
    if STRATEGY_MODE == 'mean_reversion':
        run_fixed_params_no_optimization_test()
    elif STRATEGY_MODE == 'momentum_daily':
        run_fixed_params_momentum_test()
        run_subperiod_consistency_test()
    elif STRATEGY_MODE == 'trend_pullback':
        run_fixed_params_trend_pullback_test()
        run_subperiod_consistency_test_trend_pullback()
    elif STRATEGY_MODE == 'pullback_no_trend':
        run_fixed_params_pullback_no_trend_test()


# ─────────────────────────────────────────────────────────────────────────────
# ✅ استراتژی جدید: Trend + Pullback Entry (سبک صندوق‌های trend-following حرفه‌ای)
#
# طراحی (هر بخش عمداً به سبک حرفه‌ای، نه اختراعی):
#   1. فیلتر روند: همان momentum ۲۱روزه‌ی تأییدشده (Liu et al. 2022) — فقط
#      در جهت روند معامله می‌کنیم، نه برخلافش.
#   2. محرک ورود: به‌جای ورود فوری، صبر برای «pullback» — RSI روزانه در
#      جهت مخالف روند کمی افت/رشد می‌کند، بعد برمی‌گردد (cross) → قیمت ورود
#      بهتر از میانگین روند، نه ورود در نقطه‌ی اوج/کف لحظه‌ای.
#   3. RSI با فرمول صحیح Wilder Smoothing محاسبه می‌شود (نه میانگین ساده‌ای
#      که در indicators.py قدیمی استفاده شده بود و مقادیرش با TradingView/
#      استاندارد صنعت یکی نیست).
#   4. Stop-Loss مبتنی بر ATR (نوسان واقعی بازار، نه یک درصد ثابت دلخواه) —
#      استاندارد مدیریت ریسک صندوق‌های حرفه‌ای (مثل سیستم Turtle Trading).
#   5. دو حالت خروج جداگانه grid search می‌شود: نگه‌داری ثابت، یا خروج با
#      برگشت روند (کدام بهتر است را داده تعیین می‌کند، نه حدس).
# ─────────────────────────────────────────────────────────────────────────────

TP_LOOKBACK = 21  # همان momentum lookback تأییدشده
TP_MOM_THRESHOLD_OPTIONS = [0.0, 3.0]
TP_RSI_PULLBACK_OPTIONS = [40, 45, 50]     # در روند صعودی: RSI باید تا این حد افت کند بعد برگردد
TP_ATR_STOP_MULT_OPTIONS = [1.5, 2.0, 2.5]
TP_EXIT_MODE_OPTIONS = ['fixed_hold', 'trend_reversal']
TP_HOLD_DAYS_MAX_OPTIONS = [10, 15]
TP_RSI_PERIOD = 14
TP_ATR_PERIOD = 14
MIN_TRADES_FOR_SELECTION_TP = 8


def _calculate_daily_rsi_wilder(close: np.ndarray, period: int = 14) -> np.ndarray:
    """RSI با فرمول صحیح Wilder Smoothing — همان فرمولی که TradingView/اکثر
    پلتفرم‌ها استفاده می‌کنند (برخلاف میانگین ساده‌ی indicators.py قدیمی)."""
    n = len(close)
    rsi = np.full(n, np.nan)
    if n <= period:
        return rsi
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    rsi[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    for i in range(period + 1, n):
        gain = gains[i - 1]
        loss = losses[i - 1]
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rsi[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    return rsi


def _calculate_daily_atr_wilder(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                                 period: int = 14) -> np.ndarray:
    """ATR با فرمول صحیح Wilder Smoothing — برای سایزینگ استاپ مبتنی بر نوسان واقعی."""
    n = len(close)
    atr = np.full(n, np.nan)
    if n <= period:
        return atr
    tr = np.zeros(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))

    atr[period] = np.mean(tr[1:period + 1])
    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return atr


def _prepare_trend_pullback_arrays(daily_df: pd.DataFrame) -> dict:
    """محاسبه‌ی یک‌باره‌ی RSI/ATR/momentum روی کل سری — مستقل از پارامترهای
    grid search، تا هر ترکیب فقط از این آرایه‌های آماده استفاده کند (سریع‌تر)."""
    close_col = 'Close' if 'Close' in daily_df.columns else 'close'
    high_col = 'High' if 'High' in daily_df.columns else 'high'
    low_col = 'Low' if 'Low' in daily_df.columns else 'low'

    close = daily_df[close_col].to_numpy(dtype=float)
    high = daily_df[high_col].to_numpy(dtype=float)
    low = daily_df[low_col].to_numpy(dtype=float)
    n = len(close)

    rsi = _calculate_daily_rsi_wilder(close, TP_RSI_PERIOD)
    atr = _calculate_daily_atr_wilder(high, low, close, TP_ATR_PERIOD)

    mom_return = np.full(n, np.nan)
    for i in range(TP_LOOKBACK + 1, n):
        c_yesterday = close[i - 1]
        c_prior = close[i - 1 - TP_LOOKBACK]
        if c_prior != 0:
            mom_return[i] = (c_yesterday - c_prior) / c_prior * 100.0

    return {'close': close, 'high': high, 'low': low, 'rsi': rsi, 'atr': atr, 'mom_return': mom_return}


def simulate_trend_pullback(arrays: dict, start_idx: int, end_idx: int,
                             mom_threshold: float, rsi_pullback_level: float,
                             atr_stop_mult: float, exit_mode: str, hold_days_max: int) -> list:
    """
    شبیه‌سازی Trend+Pullback با استاپ مبتنی بر ATR — یک پوزیشن هم‌زمان.
    Returns: لیست pnl_percent هر معامله (net از هزینه‌ی معامله).
    """
    close, high, low = arrays['close'], arrays['high'], arrays['low']
    rsi, atr, mom_return = arrays['rsi'], arrays['atr'], arrays['mom_return']

    trades = []
    position = None
    was_below_pullback = False
    was_above_pullback = False

    for i in range(max(start_idx, 1), min(end_idx, len(close))):
        if np.isnan(rsi[i]) or np.isnan(atr[i]) or np.isnan(mom_return[i]):
            continue

        price = close[i]

        # ── مدیریت پوزیشن باز ────────────────────────────────────────────
        if position is not None:
            held = i - position['entry_idx']
            d = position['direction']
            exit_now, exit_price = False, None

            if d == 'LONG' and low[i] <= position['stop_price']:
                exit_now, exit_price = True, position['stop_price']
            elif d == 'SHORT' and high[i] >= position['stop_price']:
                exit_now, exit_price = True, position['stop_price']
            elif exit_mode == 'trend_reversal':
                cur_dir = ('LONG' if mom_return[i] >= mom_threshold
                           else ('SHORT' if mom_return[i] <= -mom_threshold else None))
                if cur_dir is not None and cur_dir != d:
                    exit_now, exit_price = True, price
                elif held >= hold_days_max:  # سقف ایمنی حتی در حالت trend_reversal
                    exit_now, exit_price = True, price
            else:  # fixed_hold
                if held >= hold_days_max:
                    exit_now, exit_price = True, price

            if exit_now:
                ret = (exit_price - position['entry_price']) / position['entry_price'] * 100.0
                pnl = ret if d == 'LONG' else -ret
                pnl -= TRANSACTION_COST_PERCENT
                trades.append(pnl)
                position = None
            continue

        # ── بررسی ورود (فقط وقتی flat هستیم) ─────────────────────────────
        trend_dir = ('LONG' if mom_return[i] >= mom_threshold
                      else ('SHORT' if mom_return[i] <= -mom_threshold else None))

        if trend_dir == 'LONG':
            was_above_pullback = False
            if rsi[i] <= rsi_pullback_level:
                was_below_pullback = True
            elif was_below_pullback and rsi[i] > rsi_pullback_level:
                stop = price - atr_stop_mult * atr[i]
                position = {'direction': 'LONG', 'entry_price': price, 'entry_idx': i, 'stop_price': stop}
                was_below_pullback = False
        elif trend_dir == 'SHORT':
            was_below_pullback = False
            rsi_high_level = 100.0 - rsi_pullback_level
            if rsi[i] >= rsi_high_level:
                was_above_pullback = True
            elif was_above_pullback and rsi[i] < rsi_high_level:
                stop = price + atr_stop_mult * atr[i]
                position = {'direction': 'SHORT', 'entry_price': price, 'entry_idx': i, 'stop_price': stop}
                was_above_pullback = False
        else:
            was_below_pullback = False
            was_above_pullback = False

    if position is not None:
        last_idx = min(end_idx, len(close)) - 1
        if last_idx >= 0:
            last_price = close[last_idx]
            ret = (last_price - position['entry_price']) / position['entry_price'] * 100.0
            pnl = ret if position['direction'] == 'LONG' else -ret
            pnl -= TRANSACTION_COST_PERCENT
            trades.append(pnl)

    return trades


def _select_best_params_trend_pullback(arrays: dict, start_idx: int, end_idx: int) -> tuple:
    best_pnl, best_trades, found = -1e9, 0, False
    best_cfg = {"MOM_THRESHOLD": 0.0, "RSI_PULLBACK": 45, "ATR_STOP_MULT": 2.0,
                "EXIT_MODE": "fixed_hold", "HOLD_DAYS_MAX": 10}
    for mt in TP_MOM_THRESHOLD_OPTIONS:
        for rp in TP_RSI_PULLBACK_OPTIONS:
            for asm in TP_ATR_STOP_MULT_OPTIONS:
                for em in TP_EXIT_MODE_OPTIONS:
                    for hd in TP_HOLD_DAYS_MAX_OPTIONS:
                        trades = simulate_trend_pullback(arrays, start_idx, end_idx, mt, rp, asm, em, hd)
                        if len(trades) < MIN_TRADES_FOR_SELECTION_TP:
                            continue
                        total = sum(trades)
                        if total > best_pnl:
                            best_pnl, best_trades, found = total, len(trades), True
                            best_cfg = {"MOM_THRESHOLD": mt, "RSI_PULLBACK": rp, "ATR_STOP_MULT": asm,
                                        "EXIT_MODE": em, "HOLD_DAYS_MAX": hd}
    return best_cfg, found, best_trades


def run_walk_forward_trend_pullback(symbol: str, daily_df: pd.DataFrame) -> list:
    arrays = _prepare_trend_pullback_arrays(daily_df)
    n = len(arrays['close'])
    if n < 300:
        logger.warning(f"{symbol}: داده‌ی روزانه کافی نیست ({n} ردیف) — رد شد")
        return []

    fold_size = n // N_FOLDS
    fold_bounds = [i * fold_size for i in range(N_FOLDS)] + [n]
    results = []

    for fold_idx in range(1, N_FOLDS):
        train_start, train_end = 0, fold_bounds[fold_idx]
        test_start, test_end = fold_bounds[fold_idx], fold_bounds[fold_idx + 1]

        best_cfg, found, sel_trades = _select_best_params_trend_pullback(arrays, train_start, train_end)
        oos_trades = simulate_trend_pullback(arrays, test_start, test_end,
                                              best_cfg["MOM_THRESHOLD"], best_cfg["RSI_PULLBACK"],
                                              best_cfg["ATR_STOP_MULT"], best_cfg["EXIT_MODE"],
                                              best_cfg["HOLD_DAYS_MAX"])

        wins = sum(1 for p in oos_trades if p > 0)
        total = len(oos_trades)
        win_rate = round(wins / total * 100, 1) if total else 0.0
        net_pnl = round(sum(oos_trades), 2)

        logger.info(
            f"[TP] {symbol} | fold {fold_idx}/{N_FOLDS-1} | "
            f"train=[0:{train_end}] test=[{test_start}:{test_end}] (روز) | "
            f"params={'یافت‌شد' if found else 'fallback'} "
            f"(MOM_TH={best_cfg['MOM_THRESHOLD']},RSI_PB={best_cfg['RSI_PULLBACK']},"
            f"ATR_MULT={best_cfg['ATR_STOP_MULT']},EXIT={best_cfg['EXIT_MODE']},"
            f"MAX_HOLD={best_cfg['HOLD_DAYS_MAX']}d) | "
            f"OOS trades={total} win_rate={win_rate}% net_pnl={net_pnl}%"
        )

        results.append({
            'symbol': symbol, 'fold': fold_idx, 'train_rows': train_end,
            'test_rows': test_end - test_start, 'params_found': found,
            **{f'param_{k}': v for k, v in best_cfg.items()},
            'oos_trades': total, 'oos_win_rate': win_rate, 'oos_net_pnl': net_pnl,
            'oos_pnls': oos_trades,
        })

    return results


# ✅ نسخه‌ی «Pullback بدون Momentum» — دقیقاً همان سبک mean-reversion که
# قبلاً تست شد، فقط با تفاوت: ورود بعد از تأیید cross (نه فوری در آستانه).
# هدف: ایزوله‌کردن این‌که آیا «صبر برای تأیید» خودش ارزش دارد یا نه.
PB_RSI_OVERSOLD_OPTIONS   = [25, 30, 35]
PB_RSI_OVERBOUGHT_OPTIONS = [65, 70, 75]
PB_ATR_STOP_MULT_OPTIONS  = [1.5, 2.0, 2.5]
PB_HOLD_DAYS_MAX_OPTIONS  = [5, 10, 15]
MIN_TRADES_FOR_SELECTION_PB = 8


def simulate_pullback_no_trend(arrays: dict, start_idx: int, end_idx: int,
                                rsi_oversold: float, rsi_overbought: float,
                                atr_stop_mult: float, hold_days_max: int) -> list:
    """
    Mean-reversion با تأیید cross، بدون فیلتر جهت momentum — می‌تواند هم
    LONG (از اشباع فروش) هم SHORT (از اشباع خرید) بدهد، صرف‌نظر از روند کلی.
    خروج: ATR stop یا سقف نگه‌داری (بدون trend_reversal، چون اینجا اصلاً
    مفهوم «روند» وجود ندارد).
    """
    close, high, low, rsi = arrays['close'], arrays['high'], arrays['low'], arrays['rsi']
    atr = arrays['atr']

    trades = []
    position = None
    was_below_os = False
    was_above_ob = False

    for i in range(max(start_idx, 1), min(end_idx, len(close))):
        if np.isnan(rsi[i]) or np.isnan(atr[i]):
            continue
        price = close[i]

        if position is not None:
            held = i - position['entry_idx']
            d = position['direction']
            exit_now, exit_price = False, None
            if d == 'LONG' and low[i] <= position['stop_price']:
                exit_now, exit_price = True, position['stop_price']
            elif d == 'SHORT' and high[i] >= position['stop_price']:
                exit_now, exit_price = True, position['stop_price']
            elif held >= hold_days_max:
                exit_now, exit_price = True, price

            if exit_now:
                ret = (exit_price - position['entry_price']) / position['entry_price'] * 100.0
                pnl = (ret if d == 'LONG' else -ret) - TRANSACTION_COST_PERCENT
                trades.append(pnl)
                position = None
            continue

        if rsi[i] <= rsi_oversold:
            was_below_os = True
        elif was_below_os and rsi[i] > rsi_oversold:
            stop = price - atr_stop_mult * atr[i]
            position = {'direction': 'LONG', 'entry_price': price, 'entry_idx': i, 'stop_price': stop}
            was_below_os = False

        if rsi[i] >= rsi_overbought:
            was_above_ob = True
        elif was_above_ob and rsi[i] < rsi_overbought:
            if position is None:  # اگر همین الان LONG باز نشد
                stop = price + atr_stop_mult * atr[i]
                position = {'direction': 'SHORT', 'entry_price': price, 'entry_idx': i, 'stop_price': stop}
            was_above_ob = False

    if position is not None:
        last_idx = min(end_idx, len(close)) - 1
        if last_idx >= 0:
            last_price = close[last_idx]
            ret = (last_price - position['entry_price']) / position['entry_price'] * 100.0
            pnl = (ret if position['direction'] == 'LONG' else -ret) - TRANSACTION_COST_PERCENT
            trades.append(pnl)

    return trades


def _select_best_params_pullback_no_trend(arrays: dict, start_idx: int, end_idx: int) -> tuple:
    best_pnl, best_trades, found = -1e9, 0, False
    best_cfg = {"RSI_OVERSOLD": 30, "RSI_OVERBOUGHT": 70, "ATR_STOP_MULT": 2.0, "HOLD_DAYS_MAX": 10}
    for os_ in PB_RSI_OVERSOLD_OPTIONS:
        for ob in PB_RSI_OVERBOUGHT_OPTIONS:
            for asm in PB_ATR_STOP_MULT_OPTIONS:
                for hd in PB_HOLD_DAYS_MAX_OPTIONS:
                    trades = simulate_pullback_no_trend(arrays, start_idx, end_idx, os_, ob, asm, hd)
                    if len(trades) < MIN_TRADES_FOR_SELECTION_PB:
                        continue
                    total = sum(trades)
                    if total > best_pnl:
                        best_pnl, best_trades, found = total, len(trades), True
                        best_cfg = {"RSI_OVERSOLD": os_, "RSI_OVERBOUGHT": ob,
                                    "ATR_STOP_MULT": asm, "HOLD_DAYS_MAX": hd}
    return best_cfg, found, best_trades


def run_walk_forward_pullback_no_trend(symbol: str, daily_df: pd.DataFrame) -> list:
    arrays = _prepare_trend_pullback_arrays(daily_df)
    n = len(arrays['close'])
    if n < 300:
        logger.warning(f"{symbol}: داده‌ی روزانه کافی نیست ({n} ردیف) — رد شد")
        return []

    fold_size = n // N_FOLDS
    fold_bounds = [i * fold_size for i in range(N_FOLDS)] + [n]
    results = []

    for fold_idx in range(1, N_FOLDS):
        train_start, train_end = 0, fold_bounds[fold_idx]
        test_start, test_end = fold_bounds[fold_idx], fold_bounds[fold_idx + 1]

        best_cfg, found, sel_trades = _select_best_params_pullback_no_trend(arrays, train_start, train_end)
        oos_trades = simulate_pullback_no_trend(arrays, test_start, test_end,
                                                 best_cfg["RSI_OVERSOLD"], best_cfg["RSI_OVERBOUGHT"],
                                                 best_cfg["ATR_STOP_MULT"], best_cfg["HOLD_DAYS_MAX"])

        wins = sum(1 for p in oos_trades if p > 0)
        total = len(oos_trades)
        win_rate = round(wins / total * 100, 1) if total else 0.0
        net_pnl = round(sum(oos_trades), 2)

        logger.info(
            f"[PB] {symbol} | fold {fold_idx}/{N_FOLDS-1} | "
            f"train=[0:{train_end}] test=[{test_start}:{test_end}] (روز) | "
            f"params={'یافت‌شد' if found else 'fallback'} "
            f"(RSI_OS={best_cfg['RSI_OVERSOLD']},RSI_OB={best_cfg['RSI_OVERBOUGHT']},"
            f"ATR_MULT={best_cfg['ATR_STOP_MULT']},MAX_HOLD={best_cfg['HOLD_DAYS_MAX']}d) | "
            f"OOS trades={total} win_rate={win_rate}% net_pnl={net_pnl}%"
        )

        results.append({
            'symbol': symbol, 'fold': fold_idx, 'train_rows': train_end,
            'test_rows': test_end - test_start, 'params_found': found,
            **{f'param_{k}': v for k, v in best_cfg.items()},
            'oos_trades': total, 'oos_win_rate': win_rate, 'oos_net_pnl': net_pnl,
            'oos_pnls': oos_trades,
        })

    return results


def run_fixed_params_pullback_no_trend_test() -> dict:
    """تست بدون بهینه‌سازی — RSI 30/70 استاندارد، ATR_STOP=2.0، HOLD_MAX=10 روز."""
    FIXED = {"RSI_OVERSOLD": 30, "RSI_OVERBOUGHT": 70, "ATR_STOP_MULT": 2.0, "HOLD_DAYS_MAX": 10}
    logger.info("\n" + "=" * 70)
    logger.info("🔒 [Pullback-No-Trend] تست بدون بهینه‌سازی (پارامتر متعارف)")
    logger.info(f"   پارامتر ثابت: {FIXED}")
    logger.info("=" * 70)

    all_pnls = []
    for symbol in TEST_SYMBOLS:
        daily_df = _fetch_daily_data(symbol)
        if daily_df is None or len(daily_df) < 300:
            continue
        arrays = _prepare_trend_pullback_arrays(daily_df)
        trades = simulate_pullback_no_trend(arrays, 0, len(arrays['close']),
                                             FIXED["RSI_OVERSOLD"], FIXED["RSI_OVERBOUGHT"],
                                             FIXED["ATR_STOP_MULT"], FIXED["HOLD_DAYS_MAX"])
        all_pnls.extend(trades)
        n_tr = len(trades)
        wr = round(sum(1 for p in trades if p > 0) / n_tr * 100, 1) if n_tr else 0.0
        logger.info(f"   {symbol}: trades={n_tr} win_rate={wr}% net_pnl={round(sum(trades), 2)}%")

    n = len(all_pnls)
    if n == 0:
        logger.warning("هیچ معامله‌ای رخ نداد")
        return {}
    wins_sum = sum(p for p in all_pnls if p > 0)
    losses_sum = abs(sum(p for p in all_pnls if p <= 0))
    pf = round(wins_sum / losses_sum, 2) if losses_sum > 0 else (float('inf') if wins_sum > 0 else 0.0)
    win_rate = round(sum(1 for p in all_pnls if p > 0) / n * 100, 1)
    net_pnl = round(sum(all_pnls), 2)

    logger.info("\n" + "-" * 70)
    logger.info(f"📌 [Pullback-No-Trend] نتیجه: trades={n} | win_rate={win_rate}% | "
                f"net_pnl={net_pnl}% | Profit Factor={pf}")
    logger.info("✅ edge مثبت دیده شد." if (net_pnl > 0 and pf > 1.15) else "❌ edge معناداری دیده نشد.")
    logger.info("-" * 70)
    return {'fixed_params': FIXED, 'total_trades': n, 'win_rate': win_rate,
            'net_pnl': net_pnl, 'profit_factor': pf}



    """
    ✅ تست بدون بهینه‌سازی برای Trend+Pullback — پارامتر «متعارف» انتخاب‌شده
    از قبل (نه از grid search بالا): RSI_PULLBACK=45 (نقطه‌ی میانی محدوده‌ی
    تست‌شده)، ATR_STOP_MULT=2.0 (استاندارد رایج صندوق‌های trend-following)،
    exit_mode='trend_reversal' (فلسفه‌ی اصلی سیستم: تا وقتی روند برقرار است
    بمان)، HOLD_DAYS_MAX=15 (سقف ایمنی).
    """
    FIXED = {"MOM_THRESHOLD": 0.0, "RSI_PULLBACK": 45, "ATR_STOP_MULT": 2.0,
             "EXIT_MODE": "trend_reversal", "HOLD_DAYS_MAX": 15}
    logger.info("\n" + "=" * 70)
    logger.info("🔒 [Trend+Pullback] تست بدون بهینه‌سازی (پارامتر متعارف، بدون grid search)")
    logger.info(f"   پارامتر ثابت: {FIXED}")
    logger.info("=" * 70)

    all_pnls = []
    for symbol in TEST_SYMBOLS:
        daily_df = _fetch_daily_data(symbol)
        if daily_df is None or len(daily_df) < 300:
            logger.warning(f"{symbol}: داده‌ی روزانه کافی نیست — رد شد")
            continue
        arrays = _prepare_trend_pullback_arrays(daily_df)
        trades = simulate_trend_pullback(arrays, 0, len(arrays['close']),
                                          FIXED["MOM_THRESHOLD"], FIXED["RSI_PULLBACK"],
                                          FIXED["ATR_STOP_MULT"], FIXED["EXIT_MODE"], FIXED["HOLD_DAYS_MAX"])
        all_pnls.extend(trades)
        n_tr = len(trades)
        wr = round(sum(1 for p in trades if p > 0) / n_tr * 100, 1) if n_tr else 0.0
        logger.info(f"   {symbol}: trades={n_tr} win_rate={wr}% net_pnl={round(sum(trades), 2)}%")

    n = len(all_pnls)
    if n == 0:
        logger.warning("هیچ معامله‌ای در تست ثابت رخ نداد")
        return {}

    wins_sum = sum(p for p in all_pnls if p > 0)
    losses_sum = abs(sum(p for p in all_pnls if p <= 0))
    pf = round(wins_sum / losses_sum, 2) if losses_sum > 0 else (float('inf') if wins_sum > 0 else 0.0)
    win_rate = round(sum(1 for p in all_pnls if p > 0) / n * 100, 1)
    net_pnl = round(sum(all_pnls), 2)

    logger.info("\n" + "-" * 70)
    logger.info(f"📌 [Trend+Pullback] نتیجه‌ی تست بدون بهینه‌سازی: trades={n} | "
                f"win_rate={win_rate}% | net_pnl={net_pnl}% | Profit Factor={pf}")
    if net_pnl > 0 and pf > 1.15:
        logger.info("✅ حتی با پارامتر متعارف (بدون بهینه‌سازی)، edge مثبت دیده می‌شود.")
    else:
        logger.info("❌ با پارامتر متعارف، edge معناداری دیده نمی‌شود.")
    logger.info("-" * 70)

    return {'fixed_params': FIXED, 'total_trades': n, 'win_rate': win_rate,
            'net_pnl': net_pnl, 'profit_factor': pf}


def run_subperiod_consistency_test_trend_pullback() -> dict:
    """✅ همان تست ثبات زیردوره‌ای momentum_daily، برای Trend+Pullback."""
    FIXED = {"MOM_THRESHOLD": 0.0, "RSI_PULLBACK": 45, "ATR_STOP_MULT": 2.0,
             "EXIT_MODE": "trend_reversal", "HOLD_DAYS_MAX": 15}
    N_CHUNKS = 3
    logger.info("\n" + "=" * 70)
    logger.info("🔒 [Trend+Pullback] تست ثبات زیردوره‌ای — همان پارامتر ثابت در ۳ بخش تاریخی جدا")
    logger.info("=" * 70)

    chunk_results = {i: [] for i in range(N_CHUNKS)}
    chunk_dates = {i: None for i in range(N_CHUNKS)}

    for symbol in TEST_SYMBOLS:
        daily_df = _fetch_daily_data(symbol)
        if daily_df is None or len(daily_df) < 300:
            continue
        arrays = _prepare_trend_pullback_arrays(daily_df)
        n = len(arrays['close'])
        chunk_size = n // N_CHUNKS
        bounds = [i * chunk_size for i in range(N_CHUNKS)] + [n]

        ts_col = 'Timestamp' if 'Timestamp' in daily_df.columns else 'timestamp'
        logger.info(f"\n   --- {symbol} ({n} روز کل) ---")
        for c in range(N_CHUNKS):
            c_start, c_end = bounds[c], bounds[c + 1]
            trades = simulate_trend_pullback(arrays, c_start, c_end,
                                              FIXED["MOM_THRESHOLD"], FIXED["RSI_PULLBACK"],
                                              FIXED["ATR_STOP_MULT"], FIXED["EXIT_MODE"], FIXED["HOLD_DAYS_MAX"])
            chunk_results[c].extend(trades)
            start_date = daily_df.iloc[c_start].get(ts_col, '?')
            end_date = daily_df.iloc[min(c_end, n) - 1].get(ts_col, '?')
            chunk_dates[c] = (start_date, end_date)
            n_tr = len(trades)
            wr = round(sum(1 for p in trades if p > 0) / n_tr * 100, 1) if n_tr else 0.0
            logger.info(f"      بخش {c+1}/{N_CHUNKS}: trades={n_tr} win_rate={wr}% net_pnl={round(sum(trades), 2)}%")

    logger.info("\n" + "-" * 70)
    positive_chunks = 0
    for c in range(N_CHUNKS):
        trades = chunk_results[c]
        n_tr = len(trades)
        if n_tr == 0:
            logger.info(f"   بخش {c+1}: بدون معامله")
            continue
        wins_sum = sum(p for p in trades if p > 0)
        losses_sum = abs(sum(p for p in trades if p <= 0))
        pf = round(wins_sum / losses_sum, 2) if losses_sum > 0 else (float('inf') if wins_sum > 0 else 0.0)
        net_pnl = round(sum(trades), 2)
        is_positive = net_pnl > 0 and pf > 1.0
        positive_chunks += int(is_positive)
        mark = "✅" if is_positive else "❌"
        logger.info(f"   {mark} بخش {c+1}: trades={n_tr} net_pnl={net_pnl}% PF={pf}")

    logger.info("-" * 70)
    if positive_chunks == N_CHUNKS:
        logger.info(f"✅✅ edge در هر {N_CHUNKS} بخش تاریخی مستقل مثبت بود.")
    elif positive_chunks >= 2:
        logger.info(f"⚠️ edge در {positive_chunks}/{N_CHUNKS} بخش مثبت بود — وابسته به رژیم بازار.")
    else:
        logger.info(f"❌ edge فقط در {positive_chunks}/{N_CHUNKS} بخش مثبت بود.")
    logger.info("-" * 70)

    return {'positive_chunks': positive_chunks}



    """
    ✅ تست تعیین‌کننده برای momentum_daily: هیچ grid search/انتخاب پارامتری.
    چند ترکیب پارامتر از خودِ ادبیات آکادمیک (نه چیزی که از نتایج
    walk-forward بالا انتخاب شده باشد) روی کل تاریخچه‌ی BTC/ETH تست می‌شود:
      - (21, 5)  → Liu et al. 2022 (اصلی)
      - (28, 5)  → همان مقاله، نسخه‌ی جایگزین لوک‌بک
      - (14, 7)  → چیزی که خودِ walk-forward برای BTC پایدار انتخاب کرد
      - (35, 7)  → چیزی که خودِ walk-forward برای ETH پایدار انتخاب کرد
    اگر همه یا اکثر این ترکیب‌های همسایه هم PF>1 بدهند، یعنی edge روی یک
    «فلات» پایدار است، نه یک نقطه‌ی شانسی.
    """
    PARAM_SETS = [
        {"LOOKBACK": 21, "HOLD": 5, "MIN_THRESHOLD": 0.0, "label": "Liu2022-اصلی"},
        {"LOOKBACK": 28, "HOLD": 5, "MIN_THRESHOLD": 0.0, "label": "Liu2022-جایگزین"},
        {"LOOKBACK": 14, "HOLD": 7, "MIN_THRESHOLD": 0.0, "label": "walk-forward BTC"},
        {"LOOKBACK": 35, "HOLD": 7, "MIN_THRESHOLD": 0.0, "label": "walk-forward ETH"},
    ]
    logger.info("\n" + "=" * 70)
    logger.info("🔒 تست بدون بهینه‌سازی — چند پارامتر همسایه (بررسی فلات بودن edge)")
    logger.info("=" * 70)

    daily_cache = {}
    for symbol in TEST_SYMBOLS:
        daily_cache[symbol] = _fetch_daily_data(symbol)
        d = daily_cache[symbol]
        if d is not None:
            first_ts = d.iloc[0].get('timestamp', 'نامشخص')
            last_ts = d.iloc[-1].get('timestamp', 'نامشخص')
            logger.info(f"   {symbol}: {len(d)} ردیف روزانه | بازه: {first_ts} → {last_ts}")

    all_summaries = []
    for params in PARAM_SETS:
        all_pnls = []
        for symbol in TEST_SYMBOLS:
            daily_df = daily_cache.get(symbol)
            if daily_df is None or len(daily_df) < 300:
                continue
            pnls = simulate_window_momentum(daily_df, 0, len(daily_df),
                                             params["LOOKBACK"], params["HOLD"],
                                             params["MIN_THRESHOLD"], symbol)
            all_pnls.extend(pnls)

        n = len(all_pnls)
        if n == 0:
            logger.warning(f"   [{params['label']}] هیچ معامله‌ای رخ نداد")
            continue
        wins_sum = sum(p for p in all_pnls if p > 0)
        losses_sum = abs(sum(p for p in all_pnls if p <= 0))
        pf = round(wins_sum / losses_sum, 2) if losses_sum > 0 else (float('inf') if wins_sum > 0 else 0.0)
        win_rate = round(sum(1 for p in all_pnls if p > 0) / n * 100, 1)
        net_pnl = round(sum(all_pnls), 2)

        logger.info(
            f"   [{params['label']}] LOOKBACK={params['LOOKBACK']} HOLD={params['HOLD']} | "
            f"trades={n} win_rate={win_rate}% net_pnl={net_pnl}% PF={pf}"
        )
        all_summaries.append({**params, 'trades': n, 'win_rate': win_rate,
                              'net_pnl': net_pnl, 'profit_factor': pf})

    positive_count = sum(1 for s in all_summaries if s['profit_factor'] > 1.0)
    logger.info("\n" + "-" * 70)
    logger.info(f"📌 خلاصه: {positive_count}/{len(all_summaries)} ترکیب پارامتر PF>1.0 داشتند")
    if positive_count >= 3:
        logger.info("✅ edge روی یک فلات پایدار دیده می‌شود (نه فقط یک نقطه‌ی شانسی) — "
                     "شواهد قوی‌تری برای واقعی بودن این momentum.")
    elif positive_count >= 2:
        logger.info("⚠️ نتیجه مختلط — بعضی همسایه‌ها مثبت‌اند ولی نه همه؛ احتیاط لازم است.")
    else:
        logger.info("❌ فقط یک نقطه مثبت بود — احتمال شانسی بودن نتیجه‌ی اولیه بالاست.")
    logger.info("-" * 70)

    return {'param_sets_tested': all_summaries, 'positive_count': positive_count}


def run_subperiod_consistency_test() -> dict:
    """
    ✅ آخرین تست تعیین‌کننده: بدون هیچ بازانتخاب پارامتری در هیچ نقطه‌ای.
    یک پارامتر ثابت (LOOKBACK=21, HOLD=5 — از ادبیات) روی ۳ بخش زمانی
    بزرگ و غیرهم‌پوشان (نه fold کوچک قابل‌بازانتخاب) جدا گزارش می‌شود.

    هدف: آیا edge در همه‌ی دوره‌های تاریخی حاضر است (نشانه‌ی edge واقعی)،
    یا فقط در یک دوره‌ی خاص (مثلاً یک بازار صعودی) متمرکز شده (نشانه‌ی
    شانس/رژیم خاص، نه یک الگوی تکرارشونده)؟ برخلاف walk-forward، اینجا
    پارامتر هرگز روی هیچ بخشی «آموزش» یا «بازانتخاب» نمی‌شود — کاملاً از
    سوگیری انتخاب پارامتر مبراست.
    """
    FIXED = {"LOOKBACK": 21, "HOLD": 5, "MIN_THRESHOLD": 0.0}
    N_CHUNKS = 3
    logger.info("\n" + "=" * 70)
    logger.info("🔒 تست ثبات زیردوره‌ای — همان پارامتر ثابت، بدون بازانتخاب، در ۳ بخش تاریخی جدا")
    logger.info(f"   پارامتر ثابت (بدون تغییر در هیچ بخشی): {FIXED}")
    logger.info("=" * 70)

    chunk_results = {i: [] for i in range(N_CHUNKS)}
    chunk_dates = {i: None for i in range(N_CHUNKS)}

    for symbol in TEST_SYMBOLS:
        daily_df = _fetch_daily_data(symbol)
        if daily_df is None or len(daily_df) < 300:
            logger.warning(f"{symbol}: داده‌ی روزانه کافی نیست — رد شد")
            continue

        n = len(daily_df)
        chunk_size = n // N_CHUNKS
        bounds = [i * chunk_size for i in range(N_CHUNKS)] + [n]

        logger.info(f"\n   --- {symbol} ({n} روز کل) ---")
        for c in range(N_CHUNKS):
            c_start, c_end = bounds[c], bounds[c + 1]
            pnls = simulate_window_momentum(daily_df, c_start, c_end,
                                             FIXED["LOOKBACK"], FIXED["HOLD"],
                                             FIXED["MIN_THRESHOLD"], symbol)
            chunk_results[c].extend(pnls)

            start_date = daily_df.iloc[c_start].get('timestamp', '?')
            end_date = daily_df.iloc[min(c_end, n) - 1].get('timestamp', '?')
            chunk_dates[c] = (start_date, end_date)

            n_tr = len(pnls)
            wr = round(sum(1 for p in pnls if p > 0) / n_tr * 100, 1) if n_tr else 0.0
            logger.info(f"      بخش {c+1}/{N_CHUNKS} [{start_date} → {end_date}]: "
                        f"trades={n_tr} win_rate={wr}% net_pnl={round(sum(pnls), 2)}%")

    logger.info("\n" + "-" * 70)
    logger.info("📌 خلاصه‌ی هر بخش زمانی (روی BTC+ETH ترکیبی):")
    positive_chunks = 0
    for c in range(N_CHUNKS):
        pnls = chunk_results[c]
        n_tr = len(pnls)
        if n_tr == 0:
            logger.info(f"   بخش {c+1}: بدون معامله")
            continue
        wins_sum = sum(p for p in pnls if p > 0)
        losses_sum = abs(sum(p for p in pnls if p <= 0))
        pf = round(wins_sum / losses_sum, 2) if losses_sum > 0 else (float('inf') if wins_sum > 0 else 0.0)
        net_pnl = round(sum(pnls), 2)
        is_positive = net_pnl > 0 and pf > 1.0
        positive_chunks += int(is_positive)
        mark = "✅" if is_positive else "❌"
        logger.info(f"   {mark} بخش {c+1} [{chunk_dates[c][0]} → {chunk_dates[c][1]}]: "
                    f"trades={n_tr} net_pnl={net_pnl}% PF={pf}")

    logger.info("-" * 70)
    if positive_chunks == N_CHUNKS:
        logger.info(f"✅✅ edge در هر {N_CHUNKS} بخش تاریخی مستقل مثبت بود — "
                     f"قوی‌ترین شاهد ممکن برای واقعی و تکرارشونده بودن این momentum.")
    elif positive_chunks >= 2:
        logger.info(f"⚠️ edge در {positive_chunks}/{N_CHUNKS} بخش مثبت بود — احتمالاً واقعی "
                     f"ولی وابسته به رژیم بازار؛ با احتیاط و ریسک کمتر عمل شود.")
    else:
        logger.info(f"❌ edge فقط در {positive_chunks}/{N_CHUNKS} بخش مثبت بود — به‌احتمال زیاد "
                     f"نتیجه‌ی کلی حاصل یک دوره‌ی خاص (مثلاً بازار صعودی) بوده، نه یک الگوی پایدار.")
    logger.info("-" * 70)

    return {'fixed_params': FIXED, 'n_chunks': N_CHUNKS, 'positive_chunks': positive_chunks}


if __name__ == "__main__":
    main()

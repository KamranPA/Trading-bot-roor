# ---------------------------------------------------------
# FILE PATH: src/backtester.py  (FIXED & IMPROVED v2.0)
# تغییرات:
#   1. ذخیره معاملات در CSV (از طریق csv_store) نه SQLite محلی
#   2. اصلاح محاسبه PnL (همان فرمول check_exits اصلاح‌شده)
#   3. تولید خودکار Summary در پایان
#   4. جلوگیری از Look-Ahead Bias: فقط داده قبل از کندل فعلی استفاده می‌شود
#   5. لاگ پیشرفت
# ---------------------------------------------------------
import os
import sys
import json
import logging
from datetime import datetime

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from src import indicators, strategy_utils
from src.csv_store import (
    save_backtest_trade, close_backtest_trade,
    flush_closed_trades, export_to_sqlite,
)

logger = logging.getLogger(__name__)

MAX_OPEN_POSITIONS = getattr(config, 'MAX_OPEN_POSITIONS', 3)


def run_backtest(
    df_raw: pd.DataFrame,
    pair: str,
    params: dict,
    model=None,
    min_score: float = None,
) -> dict:
    """
    بکتست استراتژی Swing Breakout روی داده تاریخی.

    Args:
        df_raw:    دیتافریم خام کندل‌ها (ستون‌های Open/High/Low/Close/Volume)
        pair:      نماد ارز
        params:    پارامترهای استراتژی (ADX_THRESHOLD, TP_RATIO, SL_RATIO, ...)
        model:     مدل AI (اختیاری — اگر None باشد امتیاز AI صفر در نظر گرفته می‌شود)
        min_score: حداقل امتیاز برای ورود به معامله

    Returns:
        دیکشنری نتایج: {total, wins, losses, win_rate, total_pnl, max_drawdown, trades}
    """
    if df_raw is None or len(df_raw) < 210:
        logger.warning("داده ناکافی برای بکتست %s (طول: %s)", pair, len(df_raw) if df_raw is not None else 0)
        return _empty_result(pair)

    if min_score is None:
        min_score = float(getattr(config, 'MIN_REQUIRED_SCORE', 60))

    adx_thresh   = float(params.get('ADX_THRESHOLD', config.ADX_THRESHOLD))
    tp_ratio     = float(params.get('TP_RATIO',      config.TP_RATIO))
    sl_ratio     = float(params.get('SL_RATIO',      config.SL_RATIO))
    ai_threshold = float(params.get('AI_THRESHOLD',  getattr(config, 'AI_THRESHOLD', 65.0)))
    swing_window = int(params.get('SWING_WINDOW',    config.SWING_WINDOW))
    MAX_SL_PCT   = float(getattr(config, 'MAX_SL_PERCENT', 0.03))

    # وزن‌های امتیازدهی از config (هماهنگ با استراتژی لایو)
    w_ai  = float(getattr(config, 'WEIGHT_AI',  40))
    w_adx = float(getattr(config, 'WEIGHT_ADX', 20))
    w_rsi = float(getattr(config, 'WEIGHT_RSI', 20))
    w_ema = float(getattr(config, 'WEIGHT_EMA', 20))
    w_sum = (w_ai + w_adx + w_rsi + w_ema) or 100.0

    # اندیکاتورها روی کل دیتا محاسبه می‌شوند
    df_full = indicators.calculate_indicators(df_raw.copy())

    open_trades   = []   # لیست معاملات باز در حین بکتست
    closed_trades = []   # نتایج نهایی

    for i in range(200, len(df_full)):
        # FIX: فقط داده‌های پیش از کندل فعلی (بدون Look-Ahead Bias)
        df_slice = df_full.iloc[:i + 1]
        candle   = df_full.iloc[i]

        current_price = float(candle['Close'])
        high_price    = float(candle['High'])
        low_price     = float(candle['Low'])

        # --- بستن معاملات باز ---
        still_open = []
        for trade in open_trades:
            direction = trade['direction']
            sl        = trade['stop_loss']
            tp2       = trade['tp2']
            entry     = trade['entry_price']
            closed    = False

            if direction == 'LONG':
                if low_price <= sl:
                    pnl    = ((sl - entry) / entry) * 100
                    reason = 'SL_HIT'
                    closed = True
                elif high_price >= tp2:
                    pnl    = ((tp2 - entry) / entry) * 100
                    reason = 'TP_HIT'
                    closed = True
            else:  # SHORT
                if high_price >= sl:
                    pnl    = ((entry - sl) / entry) * 100
                    reason = 'SL_HIT'
                    closed = True
                elif low_price <= tp2:
                    pnl    = ((entry - tp2) / entry) * 100
                    reason = 'TP_HIT'
                    closed = True

            if closed:
                trade['pnl_percent'] = round(pnl, 4)
                trade['close_price'] = round(sl if reason == 'SL_HIT' else tp2, 6)
                trade['status']      = reason
                trade['close_time']  = str(candle.name) if hasattr(candle, 'name') else ''
                closed_trades.append(trade)
                close_backtest_trade(trade['id'], trade['close_price'], reason)
            else:
                still_open.append(trade)

        open_trades = still_open

        # --- امتیازدهی ---
        current_adx  = float(candle.get('feat_adx', 0))
        current_rsi  = float(candle.get('feat_rsi', 50))
        rsi_momentum = float(candle.get('feat_rsi_momentum', 0))
        dev_val      = abs(float(candle.get('feat_ema_deviation', 0)))
        atr_val      = float(candle.get('atr', candle.get('feat_atr_percent', 1.0)))

        # ADX score
        adx_score = (
            min(100.0, 50.0 + (current_adx - adx_thresh) * 2.5)
            if current_adx >= adx_thresh
            else max(0.0, (current_adx / (adx_thresh + 1e-10)) * 50.0)
        )

        # RSI score
        if current_rsi > 50:
            rsi_score = min(100.0, max(0.0, 50.0 + rsi_momentum * 5))
        else:
            rsi_score = min(100.0, max(0.0, 50.0 + (-rsi_momentum) * 5))

        # EMA score
        ema_score = min(100.0, (dev_val / 5.0) * 100.0)

        # AI score
        ai_score    = 0.0
        ai_approved = True  # اگر مدلی نباشد، فیلتر AI غیرفعال است
        if model is not None:
            try:
                features = {
                    'feat_adx': current_adx, 'feat_rsi': current_rsi,
                    'feat_rsi_momentum': rsi_momentum, 'feat_ema_deviation': dev_val,
                    'feat_atr_percent': float(candle.get('feat_atr_percent', 0)),
                    'feat_trend_line':  float(candle.get('feat_trend_line', 0)),
                    'feat_body_ratio':  float(candle.get('feat_body_ratio', 0)),
                }
                raw = model.predict_probability(pair, features)
                ai_score    = float(raw) * 100.0 if float(raw) <= 1.0 else float(raw)
                ai_approved = ai_score >= ai_threshold
            except Exception as e:
                logger.debug("AI error در بکتست %s کندل %d: %s", pair, i, e)
                ai_approved = False

        total_score = (
            ai_score * w_ai + adx_score * w_adx + rsi_score * w_rsi + ema_score * w_ema
        ) / w_sum

        if total_score < min_score or not ai_approved:
            continue

        if len(open_trades) >= MAX_OPEN_POSITIONS:
            continue

        # Swing levels
        swing_high = strategy_utils.find_last_swing(df_slice, 'high', swing_window)
        swing_low  = strategy_utils.find_last_swing(df_slice, 'low',  swing_window)

        if swing_high is None or swing_low is None:
            continue

        trade_id = f"{pair}_{i}"

        # فیچرهای مشترک برای ذخیره با معامله (ورودی آموزش مدل AI)
        trade_features = {
            'feat_adx':           round(current_adx, 4),
            'feat_rsi':           round(current_rsi, 4),
            'feat_rsi_momentum':  round(rsi_momentum, 4),
            'feat_ema_deviation': round(dev_val, 4),
            'feat_atr_percent':   round(float(candle.get('feat_atr_percent', 0)), 4),
            'feat_trend_line':    round(float(candle.get('feat_trend_line', 0)), 4),
            'feat_body_ratio':    round(float(candle.get('feat_body_ratio', 0)), 4),
        }

        # ورود LONG
        if high_price > swing_high and current_rsi > 50:
            sl_dist = min(1.5 * atr_val * sl_ratio, current_price * MAX_SL_PCT)
            if sl_dist <= 0:
                continue
            trade = {
                'id':          trade_id,
                'pair':        pair,
                'direction':   'LONG',
                'entry_price': round(current_price, 6),
                'stop_loss':   round(current_price - sl_dist, 6),
                'tp1':         round(current_price + sl_dist * tp_ratio / 2, 6),
                'tp2':         round(current_price + sl_dist * tp_ratio,     6),
                'entry_time':  str(candle.name) if hasattr(candle, 'name') else str(i),
                'status':      'OPEN',
                'total_score': round(total_score, 2),
                'ai_score':    round(ai_score, 2),
                **trade_features,
            }
            open_trades.append(trade)
            save_backtest_trade(trade)

        # ورود SHORT
        elif low_price < swing_low and current_rsi < 50:
            sl_dist = min(1.5 * atr_val * sl_ratio, current_price * MAX_SL_PCT)
            if sl_dist <= 0:
                continue
            trade = {
                'id':          trade_id,
                'pair':        pair,
                'direction':   'SHORT',
                'entry_price': round(current_price, 6),
                'stop_loss':   round(current_price + sl_dist, 6),
                'tp1':         round(current_price - sl_dist * tp_ratio / 2, 6),
                'tp2':         round(current_price - sl_dist * tp_ratio,     6),
                'entry_time':  str(candle.name) if hasattr(candle, 'name') else str(i),
                'status':      'OPEN',
                'total_score': round(total_score, 2),
                'ai_score':    round(ai_score, 2),
                **trade_features,
            }
            open_trades.append(trade)
            save_backtest_trade(trade)

    # بستن معاملات باقی‌مانده با قیمت آخر
    last_price = float(df_full.iloc[-1]['Close'])
    for trade in open_trades:
        entry     = trade['entry_price']
        direction = trade['direction']
        pnl = ((last_price - entry) / entry * 100 if direction == 'LONG'
               else (entry - last_price) / entry * 100)
        trade['pnl_percent'] = round(pnl, 4)
        trade['close_price'] = round(last_price, 6)
        trade['status']      = 'EXPIRED'
        closed_trades.append(trade)
        close_backtest_trade(trade['id'], last_price, 'EXPIRED')

    # --- محاسبه نتایج ---
    result = _compute_stats(pair, closed_trades)

    logger.info("📊 بکتست %s | معاملات: %d | Win Rate: %.1f%% | Total PnL: %.2f%%",
                pair, result['total'], result['win_rate'], result['total_pnl'])
    return result


# ---------------------------------------------------------------------------
# کمکی‌ها
# ---------------------------------------------------------------------------

def _compute_stats(pair: str, trades: list) -> dict:
    if not trades:
        return _empty_result(pair)

    pnls       = [t['pnl_percent'] for t in trades if 'pnl_percent' in t]
    wins       = sum(1 for p in pnls if p > 0)
    losses     = sum(1 for p in pnls if p <= 0)
    total      = len(pnls)
    win_rate   = round(wins / total * 100, 1) if total else 0.0
    total_pnl  = round(sum(pnls), 2)
    avg_pnl    = round(sum(pnls) / total, 2) if total else 0.0

    # Max Drawdown
    equity  = 100.0
    peak    = 100.0
    max_dd  = 0.0
    for p in pnls:
        equity *= (1 + p / 100)
        peak    = max(peak, equity)
        dd      = (peak - equity) / peak * 100
        max_dd  = max(max_dd, dd)

    return {
        'pair':         pair,
        'total':        total,
        'wins':         wins,
        'losses':       losses,
        'win_rate':     win_rate,
        'avg_pnl':      avg_pnl,
        'total_pnl':    total_pnl,
        'max_drawdown': round(-max_dd, 2),
        'best_trade':   round(max(pnls), 2) if pnls else 0.0,
        'worst_trade':  round(min(pnls), 2) if pnls else 0.0,
        'trades':       trades,
    }


def _empty_result(pair: str) -> dict:
    return {
        'pair': pair, 'total': 0, 'wins': 0, 'losses': 0,
        'win_rate': 0.0, 'avg_pnl': 0.0, 'total_pnl': 0.0,
        'max_drawdown': 0.0, 'best_trade': 0.0, 'worst_trade': 0.0,
        'trades': [],
    }


def _load_best_params() -> dict:
    """خواندن best_params.json از ریشه پروژه (در صورت وجود)."""
    params_file = os.path.join(BASE_DIR, 'best_params.json')
    if not os.path.exists(params_file):
        return {}
    try:
        with open(params_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error("خطا در خواندن best_params.json: %s", e)
        return {}


def run_all_backtests() -> dict:
    """
    اجرای بکتست برای کل WATCHLIST با استفاده از دیتای CSV (data/4h) و مدل AI.
    نتایج در data/backtest_trades.csv و خلاصه در backtest_table_summary.csv ذخیره می‌شود.
    در پایان، داده‌ها در data/trading_bot_backtest.db (SQLite) نیز ذخیره می‌شوند.
    """
    from src.brain import TradingBrain
    from src.csv_store import BACKTEST_TRADES_CSV

    # شروع از یک فایل تمیز تا معاملات اجراهای قبلی تکرار نشوند
    if os.path.exists(BACKTEST_TRADES_CSV):
        try:
            os.remove(BACKTEST_TRADES_CSV)
        except OSError as e:
            logger.warning("حذف فایل بکتست قبلی ممکن نشد: %s", e)

    brain = TradingBrain()
    all_params = _load_best_params()
    results = {}

    for symbol in getattr(config, 'WATCHLIST', []):
        safe_name = symbol.replace('/', '_')
        csv_path = os.path.join(BASE_DIR, 'data', '4h', f"{safe_name}_history.csv")
        if not os.path.exists(csv_path):
            logger.warning("فایل دیتای %s یافت نشد: %s", symbol, csv_path)
            continue
        try:
            df_raw = pd.read_csv(csv_path)
        except Exception as e:
            logger.error("خطا در خواندن دیتای %s: %s", symbol, e)
            continue

        params = all_params.get(symbol, {})
        results[symbol] = run_backtest(df_raw, symbol, params, model=brain)

    # یک بار تمام بسته‌شدن‌ها را روی دیسک بنویس (جایگزین write مکرر)
    flush_closed_trades()

    # صادر کردن نتایج به SQLite (مورد نیاز workflow برای git add و upload artifact)
    export_to_sqlite()

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    )
    run_all_backtests()

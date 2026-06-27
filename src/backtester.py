"""
FILE PATH: src/backtester.py (v3.2 - Volume Filter Aligned)
تغییرات نسبت به v3.1:
  - فیلتر حجم به صورت per-candle (یکسان با strategy.py لایو)
  - _get_volume_threshold() مشترک با strategy.py
  - _passes_volume_filter() روی candle (نه DataFrame کامل)
  - حذف _apply_volume_filter() که روی DataFrame کامل کار می‌کرد
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from src import strategy_utils
from src.indicators import TechnicalIndicators
from src.csv_store import (
    save_backtest_trade, close_backtest_trade,
    flush_closed_trades, export_to_sqlite,
)

logger = logging.getLogger(__name__)

MAX_OPEN_POSITIONS = getattr(config, 'MAX_OPEN_POSITIONS', 999)
MAX_SL_PERCENT     = float(getattr(config, 'MAX_SL_PERCENT',      0.05))
MIN_REQUIRED_SCORE = float(getattr(config, 'MIN_REQUIRED_SCORE',  65))

WEIGHT_AI  = float(getattr(config, 'WEIGHT_AI',  40))
WEIGHT_ADX = float(getattr(config, 'WEIGHT_ADX', 20))
WEIGHT_RSI = float(getattr(config, 'WEIGHT_RSI', 20))
WEIGHT_EMA = float(getattr(config, 'WEIGHT_EMA', 20))

REQUIRED_FEATURES = [
    'feat_adx', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line',
    'feat_ema_deviation', 'feat_rsi_momentum', 'feat_body_ratio',
]


# ─── Volume Filter (یکسان با strategy.py) ────────────────────────────────────

def _get_volume_threshold(symbol: str) -> float:
    """
    خواندن آستانه حجم برای یک symbol.
    هر دو فرمت را پشتیبانی می‌کند: 'BTCUSDT' و 'BTC/USDT'
    """
    thresholds = getattr(config, 'VOLUME_THRESHOLDS', {})
    if symbol in thresholds:
        return float(thresholds[symbol])
    alt = symbol.replace('/', '')
    if alt in thresholds:
        return float(thresholds[alt])
    return 0.0


def _passes_volume_filter(candle: pd.Series, symbol: str) -> bool:
    """
    بررسی فیلتر حجم برای یک کندل — رفتار کاملاً یکسان با strategy.py
    Returns True اگر فیلتر غیرفعال باشد یا کندل آستانه را رد کند.
    """
    if not getattr(config, 'ENABLE_VOLUME_FILTER', False):
        return True

    threshold = _get_volume_threshold(symbol)
    if threshold <= 0:
        return True

    vol = candle.get('volume', candle.get('Volume', 0))
    try:
        current_volume = float(vol)
    except (TypeError, ValueError):
        return True

    if current_volume < threshold:
        return False
    return True


# ─── توابع کمکی ──────────────────────────────────────────────────────────────

def _to_brain_symbol(symbol: str) -> str:
    """BTCUSDT → BTC/USDT برای brain.py"""
    if '/' not in symbol and 'USDT' in symbol:
        base = symbol.replace('USDT', '')
        return f"{base}/USDT"
    return symbol


def _normalize_dataframe(df: pd.DataFrame, symbol: str = "UNKNOWN") -> Tuple[pd.DataFrame, bool]:
    col_map  = {col: col.lower() for col in df.columns}
    df_norm  = df.rename(columns=col_map)
    required = ['close', 'high', 'low', 'open']
    missing  = [c for c in required if c not in df_norm.columns]
    if missing:
        logger.error(f"❌ {symbol}: ستون‌های الزامی وجود ندارند: {missing}")
        return df_norm, False
    return df_norm, True


def _extract_features_for_model(candle: pd.Series, symbol: str = "UNKNOWN") -> Dict:
    return {
        'feat_adx':           float(candle.get('feat_adx',           candle.get('ADX', 0))),
        'feat_atr_percent':   float(candle.get('feat_atr_percent',   candle.get('ATR', 1.0)) or 0),
        'feat_rsi':           float(candle.get('feat_rsi',           candle.get('RSI', 50))),
        'feat_trend_line':    float(candle.get('feat_trend_line',    candle.get('Trend_line', 0))),
        'feat_ema_deviation': abs(float(candle.get('feat_ema_deviation', candle.get('EMA_diff', 0)))),
        'feat_rsi_momentum':  float(candle.get('feat_rsi_momentum',  candle.get('RSI_momentum', 0))),
        'feat_body_ratio':    float(candle.get('feat_body_ratio',    candle.get('Body_ratio', 0))),
    }


def _validate_features(features: Dict, symbol: str = "UNKNOWN") -> bool:
    for feat_name in REQUIRED_FEATURES:
        if feat_name not in features:
            return False
        val = features[feat_name]
        if pd.isna(val) or not np.isfinite(val):
            return False
    return True


# ─── بکتست اصلی ──────────────────────────────────────────────────────────────

def run_backtest(
    df_raw: pd.DataFrame,
    pair: str,
    params: dict,
    model=None,
    min_score: float = None,
) -> dict:

    logger.info(f"\n{'='*70}")
    logger.info(f"شروع بکتست برای {pair}")

    if df_raw is None or len(df_raw) < 210:
        return _empty_result(pair)

    df_norm, cols_ok = _normalize_dataframe(df_raw.copy(), symbol=pair)
    if not cols_ok:
        return _empty_result(pair)

    df_full, meta = TechnicalIndicators.calculate_all_features(df_norm, symbol=pair)
    if not meta.get('success', False):
        logger.error(f"❌ محاسبه اندیکاتورها برای {pair} ناموفق")
        return _empty_result(pair)

    logger.info(f"✅ {meta['valid_rows']} ردیف معتبر")

    # اضافه کردن ستون‌های Capitalized برای strategy_utils.find_last_swing
    # که از df['High'] و df['Low'] استفاده می‌کند — یکسان با optimizer.py
    # حذف ستون‌های تکراری قبل از اضافه کردن aliases
    df_full = df_full.loc[:, ~df_full.columns.duplicated(keep='first')]
    for _lower, _upper in [('high','High'),('low','Low'),('open','Open'),
                            ('close','Close'),('volume','Volume')]:
        if _lower in df_full.columns and _upper not in df_full.columns:
            df_full[_upper] = df_full[_lower].to_numpy()

    adx_thresh   = float(params.get('ADX_THRESHOLD', config.ADX_THRESHOLD))
    tp_ratio     = float(params.get('TP_RATIO',       config.TP_RATIO))
    sl_ratio     = float(params.get('SL_RATIO',       config.SL_RATIO))
    ai_threshold = float(params.get('AI_THRESHOLD',   getattr(config, 'AI_THRESHOLD', 65.0)))
    swing_window = int(params.get('SWING_WINDOW',     config.SWING_WINDOW))

    if min_score is None:
        min_score = float(getattr(config, 'MIN_REQUIRED_SCORE', 65))

    brain_pair = _to_brain_symbol(pair)

    open_trades       = []
    closed_trades     = []
    signals_generated = 0

    for i in range(200, len(df_full)):
        df_slice = df_full.iloc[:i + 1]
        candle   = df_full.iloc[i]

        try:
            current_price = float(candle['close'])
            high_price    = float(candle['high'])
            low_price     = float(candle['low'])
        except (KeyError, ValueError, TypeError):
            continue

        # ── بستن معاملات باز ────────────────────────────────────────────────
        still_open = []
        for trade in open_trades:
            direction = trade['direction']
            sl        = trade['stop_loss']
            tp2       = trade['tp2']
            entry     = trade['entry_price']
            closed    = False; pnl = 0; reason = None

            if direction == 'LONG':
                if low_price <= sl:
                    pnl = ((sl  - entry) / entry) * 100; reason = 'SL_HIT'; closed = True
                elif high_price >= tp2:
                    pnl = ((tp2 - entry) / entry) * 100; reason = 'TP_HIT'; closed = True
            else:
                if high_price >= sl:
                    pnl = ((entry - sl)  / entry) * 100; reason = 'SL_HIT'; closed = True
                elif low_price <= tp2:
                    pnl = ((entry - tp2) / entry) * 100; reason = 'TP_HIT'; closed = True

            if closed:
                trade['pnl_percent'] = round(pnl, 4)
                trade['close_price'] = round(sl if reason == 'SL_HIT' else tp2, 6)
                trade['status']      = reason
                trade['close_time']  = str(i)
                closed_trades.append(trade)
                close_backtest_trade(trade['id'], trade['close_price'], reason)
            else:
                still_open.append(trade)
        open_trades = still_open

        # ── فیلتر حجم (per-candle — یکسان با strategy.py لایو) ─────────────
        if not _passes_volume_filter(candle, pair):
            continue

        # ── score ها ────────────────────────────────────────────────────────
        current_adx  = float(candle.get('feat_adx',           candle.get('ADX', 0)))
        current_rsi  = float(candle.get('feat_rsi',           candle.get('RSI', 50)))
        rsi_momentum = float(candle.get('feat_rsi_momentum',  candle.get('RSI_momentum', 0)))
        dev_val      = abs(float(candle.get('feat_ema_deviation', candle.get('EMA_diff', 0))))

        # ATR مطلق (نه درصدی)
        atr_raw = float(candle.get('atr', candle.get('ATR', 0)) or 0)
        if atr_raw == 0:
            atr_pct = float(candle.get('feat_atr_percent', 1.0) or 1.0)
            atr_raw = (atr_pct / 100.0) * current_price if atr_pct > 1.0 else atr_pct * current_price
        atr_val = atr_raw if atr_raw > 1.0 else current_price * 0.01

        adx_score = (min(100.0, 50.0 + (current_adx - adx_thresh) * 2.5)
                     if current_adx >= adx_thresh
                     else max(0.0, (current_adx / (adx_thresh + 1e-10)) * 50.0))

        rsi_score = (min(100.0, max(0.0, 50.0 + rsi_momentum * 5))
                     if current_rsi > 50
                     else min(100.0, max(0.0, 50.0 + (-rsi_momentum) * 5)))

        ema_score = min(100.0, (dev_val / 5.0) * 100.0)

        # ── AI score ────────────────────────────────────────────────────────
        ai_score    = 0.0
        ai_approved = True

        model_active = (
            model is not None
            and hasattr(model, 'has_model')
            and model.has_model(brain_pair)
        )

        if model_active:
            try:
                features = _extract_features_for_model(candle, pair)
                if not _validate_features(features, pair):
                    ai_approved = False
                else:
                    raw = model.predict_probability(brain_pair, features)
                    if raw is not None:
                        ai_score    = float(raw) * 100.0 if float(raw) <= 1.0 else float(raw)
                        ai_approved = ai_score >= ai_threshold
            except Exception as e:
                logger.debug(f"⚠️ {pair} کندل {i}: خطا در AI - {e}")
                ai_approved = False

        w_ai_eff  = WEIGHT_AI if model_active else 0.0
        w_sum_eff = (w_ai_eff + WEIGHT_ADX + WEIGHT_RSI + WEIGHT_EMA) or 100.0
        total_score = (
            ai_score * w_ai_eff +
            adx_score * WEIGHT_ADX +
            rsi_score * WEIGHT_RSI +
            ema_score * WEIGHT_EMA
        ) / w_sum_eff

        if total_score < min_score or not ai_approved:
            continue

        if len(open_trades) >= MAX_OPEN_POSITIONS:
            continue

        swing_high = strategy_utils.find_last_swing(df_slice, 'high', swing_window)
        swing_low  = strategy_utils.find_last_swing(df_slice, 'low',  swing_window)

        if swing_high is None or swing_low is None:
            continue

        trade_id = f"{pair}_{i}"

        if high_price > swing_high and current_rsi > 50:
            sl_dist = min(1.5 * atr_val * sl_ratio, current_price * MAX_SL_PERCENT)
            if sl_dist <= 0:
                continue
            trade = {
                'id': trade_id, 'pair': pair, 'direction': 'LONG',
                'entry_price': round(current_price, 6),
                'stop_loss':   round(current_price - sl_dist, 6),
                'tp1':         round(current_price + sl_dist * tp_ratio / 2, 6),
                'tp2':         round(current_price + sl_dist * tp_ratio,     6),
                'entry_time':  str(i), 'status': 'OPEN',
                'total_score': round(total_score, 2),
                'ai_score':    round(ai_score,    2),
                'feat_adx':    round(current_adx, 4),
                'feat_rsi':    round(current_rsi, 4),
            }
            open_trades.append(trade)
            save_backtest_trade(trade)
            signals_generated += 1

        elif low_price < swing_low and current_rsi < 50:
            sl_dist = min(1.5 * atr_val * sl_ratio, current_price * MAX_SL_PERCENT)
            if sl_dist <= 0:
                continue
            trade = {
                'id': trade_id, 'pair': pair, 'direction': 'SHORT',
                'entry_price': round(current_price, 6),
                'stop_loss':   round(current_price + sl_dist, 6),
                'tp1':         round(current_price - sl_dist * tp_ratio / 2, 6),
                'tp2':         round(current_price - sl_dist * tp_ratio,     6),
                'entry_time':  str(i), 'status': 'OPEN',
                'total_score': round(total_score, 2),
                'ai_score':    round(ai_score,    2),
                'feat_adx':    round(current_adx, 4),
                'feat_rsi':    round(current_rsi, 4),
            }
            open_trades.append(trade)
            save_backtest_trade(trade)
            signals_generated += 1

    # ── بستن معاملات باقی‌مانده ─────────────────────────────────────────────
    last_price = float(df_full.iloc[-1]['close'])
    for trade in open_trades:
        entry     = trade['entry_price']
        direction = trade['direction']
        pnl = ((last_price - entry) / entry * 100
               if direction == 'LONG'
               else (entry - last_price) / entry * 100)
        trade['pnl_percent'] = round(pnl, 4)
        trade['close_price'] = round(last_price, 6)
        trade['status']      = 'EXPIRED'
        closed_trades.append(trade)
        close_backtest_trade(trade['id'], last_price, 'EXPIRED')

    result = _compute_stats(pair, closed_trades)
    logger.info(
        f"✅ {pair}: {result['total']} معامله | "
        f"WR: {result['win_rate']}% | PnL: {result['total_pnl']}%"
    )
    return result


# ─── آمار ────────────────────────────────────────────────────────────────────

def _compute_stats(pair: str, trades: list) -> dict:
    if not trades:
        return _empty_result(pair)
    pnls = [t['pnl_percent'] for t in trades if 'pnl_percent' in t]
    if not pnls:
        return _empty_result(pair)
    wins   = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p <= 0)
    total  = len(pnls)
    equity = 100.0; peak = 100.0; max_dd = 0.0
    for p in pnls:
        equity *= (1 + p / 100)
        peak    = max(peak, equity)
        dd      = (peak - equity) / peak * 100 if peak > 0 else 0
        max_dd  = max(max_dd, dd)
    wins_sum   = sum(p for p in pnls if p > 0)
    losses_sum = abs(sum(p for p in pnls if p < 0))
    pf = (round(wins_sum / losses_sum, 2)
          if losses_sum > 0
          else (float('inf') if wins_sum > 0 else 0.0))
    return {
        'pair':          pair,
        'total':         total,
        'wins':          wins,
        'losses':        losses,
        'win_rate':      round(wins / total * 100, 1) if total else 0.0,
        'avg_pnl':       round(sum(pnls) / total, 2)  if total else 0.0,
        'total_pnl':     round(sum(pnls), 2),
        'max_drawdown':  round(-max_dd, 2),
        'best_trade':    round(max(pnls), 2),
        'worst_trade':   round(min(pnls), 2),
        'profit_factor': pf,
        'trades':        trades,
    }


def _empty_result(pair: str) -> dict:
    return {
        'pair': pair, 'total': 0, 'wins': 0, 'losses': 0,
        'win_rate': 0.0, 'avg_pnl': 0.0, 'total_pnl': 0.0,
        'max_drawdown': 0.0, 'best_trade': 0.0, 'worst_trade': 0.0,
        'profit_factor': 0.0, 'trades': [],
    }


def _save_backtest_summary(results: Dict) -> None:
    csv_path = os.path.join(BASE_DIR, 'backtest_table_summary.csv')
    rows = []
    for symbol, result in results.items():
        rows.append({
            'pair':          result.get('pair',          symbol),
            'total':         result.get('total',         0),
            'wins':          result.get('wins',          0),
            'losses':        result.get('losses',        0),
            'win_rate':      result.get('win_rate',      0.0),
            'avg_pnl':       result.get('avg_pnl',       0.0),
            'total_pnl':     result.get('total_pnl',     0.0),
            'max_drawdown':  result.get('max_drawdown',  0.0),
            'best_trade':    result.get('best_trade',    0.0),
            'worst_trade':   result.get('worst_trade',   0.0),
            'profit_factor': result.get('profit_factor', 0.0),
        })
    df_summary = pd.DataFrame(rows)
    column_order = [
        'pair', 'total', 'wins', 'losses', 'win_rate', 'avg_pnl',
        'total_pnl', 'max_drawdown', 'best_trade', 'worst_trade', 'profit_factor',
    ]
    df_summary = df_summary[column_order]
    try:
        df_summary.to_csv(csv_path, index=False, encoding='utf-8')
        logger.info(f"✅ نتایج ذخیره شد: {csv_path}")
        logger.info(df_summary.to_string(index=False))
    except Exception as e:
        logger.error(f"❌ خطا در ذخیره‌سازی: {e}")


def _load_best_params() -> dict:
    params_file = os.path.join(BASE_DIR, 'best_params.json')
    if not os.path.exists(params_file):
        return {}
    try:
        with open(params_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ خطا در خواندن best_params.json: {e}")
        return {}


def run_all_backtests() -> dict:
    from src.brain import TradingBrain
    from src.csv_store import BACKTEST_TRADES_CSV

    if os.path.exists(BACKTEST_TRADES_CSV):
        try:
            os.remove(BACKTEST_TRADES_CSV)
        except OSError:
            pass

    brain      = TradingBrain()
    all_params = _load_best_params()
    results    = {}

    for symbol in getattr(config, 'WATCHLIST', []):
        safe_name = symbol.replace('/', '_')
        csv_path  = os.path.join(BASE_DIR, 'data', '4h', f"{safe_name}_history.csv")
        if not os.path.exists(csv_path):
            logger.warning(f"⚠️ فایل دیتای {symbol} یافت نشد")
            continue
        try:
            df_raw = pd.read_csv(csv_path)
        except Exception as e:
            logger.error(f"❌ خطا در خواندن {symbol}: {e}")
            continue
        params          = all_params.get(symbol, {})
        results[symbol] = run_backtest(df_raw, symbol, params, model=brain)

    flush_closed_trades()
    export_to_sqlite()
    _save_backtest_summary(results)
    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    )
    run_all_backtests()

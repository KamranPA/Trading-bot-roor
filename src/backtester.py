"""
🔧 backtester.py (v3.0 - FULLY FIXED)
تمام مشکلات حل شده:
✅ نام ستون‌ها نرمال‌سازی شد (Close → close)
✅ Volume Filter اضافه شد
✅ Feature names یکسان‌سازی شد
✅ 7 features برای LightGBM (volume_ratio حذف شد)
✅ candle.name issues حل شد
✅ Training/Prediction مطابقت دارند
✅ Logging بهبود یافت
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

# پارامترهای پیش‌فرض از config
MAX_OPEN_POSITIONS = getattr(config, 'MAX_OPEN_POSITIONS', 3)
MAX_SL_PERCENT = float(getattr(config, 'MAX_SL_PERCENT', 0.05))
MIN_REQUIRED_SCORE = float(getattr(config, 'MIN_REQUIRED_SCORE', 65))

# Volume Filter
ENABLE_VOLUME_FILTER = getattr(config, 'ENABLE_VOLUME_FILTER', False)
VOLUME_THRESHOLDS = getattr(config, 'VOLUME_THRESHOLDS', {})

# Weights برای Scoring
WEIGHT_AI = float(getattr(config, 'WEIGHT_AI', 40))
WEIGHT_ADX = float(getattr(config, 'WEIGHT_ADX', 20))
WEIGHT_RSI = float(getattr(config, 'WEIGHT_RSI', 20))
WEIGHT_EMA = float(getattr(config, 'WEIGHT_EMA', 20))
WEIGHTS_SUM = WEIGHT_AI + WEIGHT_ADX + WEIGHT_RSI + WEIGHT_EMA

# ✅ تمام 7 features برای LightGBM (volume_ratio حذف شد)
REQUIRED_FEATURES = [
    'feat_adx',
    'feat_atr_percent',
    'feat_rsi',
    'feat_trend_line',
    'feat_ema_deviation',
    'feat_rsi_momentum',
    'feat_body_ratio',
]


def _normalize_dataframe(df: pd.DataFrame, symbol: str = "UNKNOWN") -> Tuple[pd.DataFrame, bool]:
    """
    ✅ نرمال‌سازی نام ستون‌ها
    تبدیل Close → close, High → high و غیره
    """
    col_map = {}
    for col in df.columns:
        col_lower = col.lower()
        col_map[col] = col_lower

    df_norm = df.rename(columns=col_map)

    # بررسی ستون‌های الزامی
    required = ['close', 'high', 'low', 'open']
    missing = [c for c in required if c not in df_norm.columns]

    if missing:
        logger.error(
            f"❌ {symbol}: ستون‌های الزامی وجود ندارند: {missing}. "
            f"ستون‌های موجود: {list(df_norm.columns)}"
        )
        return df_norm, False

    return df_norm, True


def _apply_volume_filter(
    df: pd.DataFrame,
    symbol: str,
    threshold: Optional[float] = None
) -> pd.DataFrame:
    """
    ✅ اعمال فیلتر حجم (بعد از محاسبه features!)
    
    Args:
        df: DataFrame با features
        symbol: نام symbol
        threshold: آستانه حجم (اگر None، از config استفاده)
    
    Returns:
        DataFrame فیلتر شده
    """
    if not ENABLE_VOLUME_FILTER:
        return df

    if 'volume' not in df.columns:
        logger.warning(f"⚠️ {symbol}: ستون 'volume' وجود ندارد، فیلتر skipped")
        return df

    if threshold is None:
        threshold = VOLUME_THRESHOLDS.get(symbol, 0)

    if threshold <= 0:
        return df

    rows_before = len(df)
    df_filtered = df[df['volume'] >= threshold].copy()
    rows_after = len(df_filtered)

    if rows_after == 0:
        logger.warning(f"⚠️ {symbol}: تمام ردیف‌ها فیلتر شدند! (threshold: {threshold:,.0f})")
        return df  # بازگرداندن اصلی
    
    logger.info(f"   Volume Filter: {rows_after}/{rows_before} ردیف ({100*rows_after/rows_before:.1f}%)")
    return df_filtered


def _extract_features_for_model(candle: pd.Series, symbol: str = "UNKNOWN") -> Dict:
    """
    ✅ استخراج 7 feature برای LightGBM
    (بدون volume_ratio)
    """
    features = {
        'feat_adx': float(candle.get('feat_adx', candle.get('ADX', 0))),
        'feat_atr_percent': float(candle.get('feat_atr_percent', candle.get('ATR', 1.0)) or 0),
        'feat_rsi': float(candle.get('feat_rsi', candle.get('RSI', 50))),
        'feat_trend_line': float(candle.get('feat_trend_line', candle.get('Trend_line', 0))),
        'feat_ema_deviation': abs(float(candle.get('feat_ema_deviation', candle.get('EMA_diff', 0)))),
        'feat_rsi_momentum': float(candle.get('feat_rsi_momentum', candle.get('RSI_momentum', 0))),
        'feat_body_ratio': float(candle.get('feat_body_ratio', candle.get('Body_ratio', 0))),
    }

    return features


def _validate_features(features: Dict, symbol: str = "UNKNOWN") -> bool:
    """
    ✅ بررسی تمام features موجود و معتبر هستند
    """
    for feat_name in REQUIRED_FEATURES:
        if feat_name not in features:
            logger.debug(f"⚠️ {symbol}: feature '{feat_name}' موجود نیست")
            return False

        val = features[feat_name]
        if pd.isna(val) or not np.isfinite(val):
            logger.debug(f"⚠️ {symbol}: feature '{feat_name}' = {val} (invalid)")
            return False

    return True


def run_backtest(
    df_raw: pd.DataFrame,
    pair: str,
    params: dict,
    model=None,
    min_score: float = None,
) -> dict:
    """
    ✅ اجرای Backtest برای یک symbol
    
    Flow:
    1. نرمال‌سازی نام ستون‌ها
    2. محاسبه تمام features
    3. اعمال Volume Filter
    4. Backtest Loop
    5. آمار و نتایج
    """

    logger.info(f"\n{'='*70}")
    logger.info(f"🚀 شروع بکتست برای {pair}")
    logger.info(f"{'='*70}")

    # ✅ STEP 1: Validation اولیه
    if df_raw is None or len(df_raw) < 210:
        logger.warning(
            f"⚠️ داده ناکافی برای بکتست {pair} "
            f"(طول: {len(df_raw) if df_raw is not None else 0}, "
            f"مورد نیاز: 210)"
        )
        return _empty_result(pair)

    # ✅ STEP 2: نرمال‌سازی ستون‌ها
    logger.info(f"1️⃣ نرمال‌سازی نام ستون‌ها...")
    df_norm, cols_ok = _normalize_dataframe(df_raw.copy(), symbol=pair)
    if not cols_ok:
        logger.error(f"❌ ستون‌های الزامی موجود نیستند")
        return _empty_result(pair)

    # ✅ STEP 3: محاسبه Features
    logger.info(f"2️⃣ محاسبه اندیکاتورهای تکنیکال...")
    df_full, meta = TechnicalIndicators.calculate_all_features(df_norm, symbol=pair)

    if not meta.get('success', False):
        logger.error(
            f"❌ محاسبه اندیکاتورها برای {pair} ناموفق: "
            f"{meta.get('missing_features', ['UNKNOWN'])}"
        )
        return _empty_result(pair)

    logger.info(f"✅ {meta['valid_rows']} ردیف معتبر")

    # ✅ STEP 4: اعمال Volume Filter (بعد از Features!)
    volume_threshold = VOLUME_THRESHOLDS.get(pair, None)
    if ENABLE_VOLUME_FILTER:
        logger.info(f"3️⃣ اعمال Volume Filter...")
        df_full = _apply_volume_filter(df_full, pair, volume_threshold)

    # ✅ STEP 5: استخراج پارامترها
    logger.info(f"4️⃣ استخراج پارامترها...")
    adx_thresh = float(params.get('ADX_THRESHOLD', config.ADX_THRESHOLD))
    tp_ratio = float(params.get('TP_RATIO', config.TP_RATIO))
    sl_ratio = float(params.get('SL_RATIO', config.SL_RATIO))
    ai_threshold = float(params.get('AI_THRESHOLD', getattr(config, 'AI_THRESHOLD', 65.0)))
    swing_window = int(params.get('SWING_WINDOW', config.SWING_WINDOW))

    if min_score is None:
        min_score = float(getattr(config, 'MIN_REQUIRED_SCORE', 65))

    logger.info(f"   ADX_THRESHOLD: {adx_thresh}")
    logger.info(f"   TP_RATIO: {tp_ratio}, SL_RATIO: {sl_ratio}")
    logger.info(f"   MIN_REQUIRED_SCORE: {min_score}")

    # ✅ STEP 6: Backtest Loop
    logger.info(f"5️⃣ اجرای حلقه بکتست...")
    open_trades = []
    closed_trades = []
    signals_generated = 0

    for i in range(200, len(df_full)):
        df_slice = df_full.iloc[:i + 1]
        candle = df_full.iloc[i]

        # ✅ استخراج قیمت‌ها (نام‌های نرمال‌سازی شده)
        try:
            current_price = float(candle['close'])
            high_price = float(candle['high'])
            low_price = float(candle['low'])
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"⚠️ {pair} کندل {i}: خطا در استخراج قیمت - {e}")
            continue

        # ────────────────────────────────────────────────────────
        # بسته شدن معاملات باز
        # ────────────────────────────────────────────────────────
        still_open = []
        for trade in open_trades:
            direction = trade['direction']
            sl = trade['stop_loss']
            tp2 = trade['tp2']
            entry = trade['entry_price']
            closed = False
            pnl = 0
            reason = None

            if direction == 'LONG':
                if low_price <= sl:
                    pnl = ((sl - entry) / entry) * 100
                    reason = 'SL_HIT'
                    closed = True
                elif high_price >= tp2:
                    pnl = ((tp2 - entry) / entry) * 100
                    reason = 'TP_HIT'
                    closed = True
            else:  # SHORT
                if high_price >= sl:
                    pnl = ((entry - sl) / entry) * 100
                    reason = 'SL_HIT'
                    closed = True
                elif low_price <= tp2:
                    pnl = ((entry - tp2) / entry) * 100
                    reason = 'TP_HIT'
                    closed = True

            if closed:
                trade['pnl_percent'] = round(pnl, 4)
                trade['close_price'] = round(sl if reason == 'SL_HIT' else tp2, 6)
                trade['status'] = reason
                trade['close_time'] = str(i)  # ✅ استفاده از index بجای candle.name
                closed_trades.append(trade)
                close_backtest_trade(trade['id'], trade['close_price'], reason)
            else:
                still_open.append(trade)

        open_trades = still_open

        # ────────────────────────────────────────────────────────
        # محاسبه Score
        # ────────────────────────────────────────────────────────
        
        # ✅ استخراج Indicators (fallback support)
        current_adx = float(candle.get('feat_adx', candle.get('ADX', 0)))
        current_rsi = float(candle.get('feat_rsi', candle.get('RSI', 50)))
        rsi_momentum = float(candle.get('feat_rsi_momentum', candle.get('RSI_momentum', 0)))
        dev_val = abs(float(candle.get('feat_ema_deviation', candle.get('EMA_diff', 0))))
        atr_val = float(candle.get('feat_atr_percent', candle.get('ATR', 1.0)) or 1.0)

        # ADX Score
        adx_score = (
            min(100.0, 50.0 + (current_adx - adx_thresh) * 2.5)
            if current_adx >= adx_thresh
            else max(0.0, (current_adx / (adx_thresh + 1e-10)) * 50.0)
        )

        # RSI Score
        if current_rsi > 50:
            rsi_score = min(100.0, max(0.0, 50.0 + rsi_momentum * 5))
        else:
            rsi_score = min(100.0, max(0.0, 50.0 + (-rsi_momentum) * 5))

        # EMA Score
        ema_score = min(100.0, (dev_val / 5.0) * 100.0)

        # ────────────────────────────────────────────────────────
        # AI Score (LightGBM Model)
        # ────────────────────────────────────────────────────────
        ai_score = 0.0
        ai_approved = True

        model_active = (
            model is not None
            and hasattr(model, 'has_model')
            and model.has_model(pair)
        )

        if model_active:
            try:
                # ✅ استخراج 7 features برای LightGBM
                features = _extract_features_for_model(candle, pair)

                # ✅ بررسی اعتبار features
                if not _validate_features(features, pair):
                    ai_approved = False
                else:
                    raw = model.predict_probability(pair, features)
                    if raw is not None:
                        ai_score = float(raw) * 100.0 if float(raw) <= 1.0 else float(raw)
                        ai_approved = ai_score >= ai_threshold

            except Exception as e:
                logger.debug(f"⚠️ {pair} کندل {i}: خطا در AI - {str(e)}")
                ai_approved = False

        # ────────────────────────────────────────────────────────
        # Total Score
        # ────────────────────────────────────────────────────────
        if model_active and ai_approved:
            total_score = (
                ai_score * WEIGHT_AI + adx_score * WEIGHT_ADX +
                rsi_score * WEIGHT_RSI + ema_score * WEIGHT_EMA
            ) / WEIGHTS_SUM
        else:
            w_ind = (WEIGHT_ADX + WEIGHT_RSI + WEIGHT_EMA) or 60.0
            total_score = (
                adx_score * WEIGHT_ADX + rsi_score * WEIGHT_RSI + ema_score * WEIGHT_EMA
            ) / w_ind

        # ────────────────────────────────────────────────────────
        # تصمیم گیری
        # ────────────────────────────────────────────────────────
        if total_score < min_score or not ai_approved:
            continue

        if len(open_trades) >= MAX_OPEN_POSITIONS:
            continue

        swing_high = strategy_utils.find_last_swing(df_slice, 'high', swing_window)
        swing_low = strategy_utils.find_last_swing(df_slice, 'low', swing_window)

        if swing_high is None or swing_low is None:
            continue

        trade_id = f"{pair}_{i}"

        # ────────────────────────────────────────────────────────
        # LONG Signal
        # ────────────────────────────────────────────────────────
        if high_price > swing_high and current_rsi > 50:
            sl_dist = min(1.5 * atr_val * sl_ratio, current_price * MAX_SL_PERCENT)
            if sl_dist <= 0:
                continue

            trade = {
                'id': trade_id,
                'pair': pair,
                'direction': 'LONG',
                'entry_price': round(current_price, 6),
                'stop_loss': round(current_price - sl_dist, 6),
                'tp1': round(current_price + sl_dist * tp_ratio / 2, 6),
                'tp2': round(current_price + sl_dist * tp_ratio, 6),
                'entry_time': str(i),  # ✅ استفاده از index
                'status': 'OPEN',
                'total_score': round(total_score, 2),
                'ai_score': round(ai_score, 2),
                # ✅ ذخیره features برای لاگ و debugging
                'feat_adx': round(current_adx, 4),
                'feat_rsi': round(current_rsi, 4),
            }
            open_trades.append(trade)
            save_backtest_trade(trade)
            signals_generated += 1

        # ────────────────────────────────────────────────────────
        # SHORT Signal
        # ────────────────────────────────────────────────────────
        elif low_price < swing_low and current_rsi < 50:
            sl_dist = min(1.5 * atr_val * sl_ratio, current_price * MAX_SL_PERCENT)
            if sl_dist <= 0:
                continue

            trade = {
                'id': trade_id,
                'pair': pair,
                'direction': 'SHORT',
                'entry_price': round(current_price, 6),
                'stop_loss': round(current_price + sl_dist, 6),
                'tp1': round(current_price - sl_dist * tp_ratio / 2, 6),
                'tp2': round(current_price - sl_dist * tp_ratio, 6),
                'entry_time': str(i),  # ✅ استفاده از index
                'status': 'OPEN',
                'total_score': round(total_score, 2),
                'ai_score': round(ai_score, 2),
                'feat_adx': round(current_adx, 4),
                'feat_rsi': round(current_rsi, 4),
            }
            open_trades.append(trade)
            save_backtest_trade(trade)
            signals_generated += 1

    # ────────────────────────────────────────────────────────
    # بسته شدن معاملات باقی مانده
    # ────────────────────────────────────────────────────────
    last_price = float(df_full.iloc[-1]['close'])
    for trade in open_trades:
        entry = trade['entry_price']
        direction = trade['direction']
        pnl = ((last_price - entry) / entry * 100 if direction == 'LONG'
               else (entry - last_price) / entry * 100)
        trade['pnl_percent'] = round(pnl, 4)
        trade['close_price'] = round(last_price, 6)
        trade['status'] = 'EXPIRED'
        closed_trades.append(trade)
        close_backtest_trade(trade['id'], last_price, 'EXPIRED')

    # ────────────────────────────────────────────────────────
    # آمار و نتایج
    # ────────────────────────────────────────────────────────
    logger.info(f"6️⃣ محاسبه آمار...")
    result = _compute_stats(pair, closed_trades)

    logger.info(f"\n✅ نتایج بکتست {pair}:")
    logger.info(f"   معاملات: {result['total']}")
    logger.info(f"   سیگنال‌های تولید شده: {signals_generated}")
    logger.info(f"   Win Rate: {result['win_rate']:.1f}%")
    logger.info(f"   Total PnL: {result['total_pnl']:.2f}%")
    logger.info(f"   Max Drawdown: {result['max_drawdown']:.2f}%")
    logger.info(f"{'='*70}\n")

    return result


def _compute_stats(pair: str, trades: list) -> dict:
    """
    ✅ محاسبه آمار معاملات
    """
    if not trades:
        return _empty_result(pair)

    pnls = [t['pnl_percent'] for t in trades if 'pnl_percent' in t]
    if not pnls:
        return _empty_result(pair)

    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p <= 0)
    total = len(pnls)
    win_rate = round(wins / total * 100, 1) if total else 0.0
    total_pnl = round(sum(pnls), 2)
    avg_pnl = round(sum(pnls) / total, 2) if total else 0.0

    # محاسبه Max Drawdown
    equity = 100.0
    peak = 100.0
    max_dd = 0.0

    for p in pnls:
        equity *= (1 + p / 100)
        peak = max(peak, equity)
        dd = (peak - equity) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)

    return {
        'pair': pair,
        'total': total,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'avg_pnl': avg_pnl,
        'total_pnl': total_pnl,
        'max_drawdown': round(-max_dd, 2),
        'best_trade': round(max(pnls), 2) if pnls else 0.0,
        'worst_trade': round(min(pnls), 2) if pnls else 0.0,
        'profit_factor': _compute_profit_factor(pnls),
        'trades': trades,
    }


def _compute_profit_factor(pnls: list) -> float:
    """
    ✅ محاسبه Profit Factor
    (مجموع برد / مجموع ضرر)
    """
    wins = sum(p for p in pnls if p > 0)
    losses = abs(sum(p for p in pnls if p < 0))

    if losses == 0:
        return float('inf') if wins > 0 else 0.0

    return round(wins / losses, 2)


def _empty_result(pair: str) -> dict:
    """
    ✅ نتیجه خالی برای بکتست ناموفق
    """
    return {
        'pair': pair,
        'total': 0,
        'wins': 0,
        'losses': 0,
        'win_rate': 0.0,
        'avg_pnl': 0.0,
        'total_pnl': 0.0,
        'max_drawdown': 0.0,
        'best_trade': 0.0,
        'worst_trade': 0.0,
        'profit_factor': 0.0,
        'trades': [],
    }


def _save_backtest_summary(results: Dict) -> None:
    """
    ✅ ذخیره‌سازی نتایج بکتست در backtest_table_summary.csv
    
    Args:
        results: Dict نتایج برای تمام symbols
    """
    csv_path = os.path.join(BASE_DIR, 'backtest_table_summary.csv')

    # آماده‌سازی داده‌های CSV
    rows = []
    for symbol, result in results.items():
        row = {
            'pair': result.get('pair', symbol),
            'total': result.get('total', 0),
            'wins': result.get('wins', 0),
            'losses': result.get('losses', 0),
            'win_rate': result.get('win_rate', 0.0),
            'avg_pnl': result.get('avg_pnl', 0.0),
            'total_pnl': result.get('total_pnl', 0.0),
            'max_drawdown': result.get('max_drawdown', 0.0),
            'best_trade': result.get('best_trade', 0.0),
            'worst_trade': result.get('worst_trade', 0.0),
            'profit_factor': result.get('profit_factor', 0.0),
        }
        rows.append(row)

    # ایجاد DataFrame
    df_summary = pd.DataFrame(rows)

    # ترتیب ستون‌ها
    column_order = [
        'pair', 'total', 'wins', 'losses', 'win_rate',
        'avg_pnl', 'total_pnl', 'max_drawdown',
        'best_trade', 'worst_trade', 'profit_factor'
    ]
    df_summary = df_summary[column_order]

    # ذخیره‌سازی
    try:
        df_summary.to_csv(csv_path, index=False, encoding='utf-8')
        logger.info(f"✅ نتایج ذخیره شد: {csv_path}")
        logger.info(f"\n📊 خلاصه نتایج:")
        logger.info(df_summary.to_string(index=False))
    except Exception as e:
        logger.error(f"❌ خطا در ذخیره‌سازی {csv_path}: {e}")


def _load_best_params() -> dict:
    """
    ✅ بارگذاری best_params.json (اختیاری)
    """
    params_file = os.path.join(BASE_DIR, 'best_params.json')
    if not os.path.exists(params_file):
        logger.info("ℹ️ best_params.json یافت نشد، از پیش‌فرض استفاده میشود")
        return {}

    try:
        with open(params_file, 'r', encoding='utf-8') as f:
            params = json.load(f)
            logger.info(f"✅ best_params.json بارگذاری شد ({len(params)} symbols)")
            return params
    except Exception as e:
        logger.error(f"❌ خطا در خواندن best_params.json: {e}")
        return {}


def run_all_backtests() -> dict:
    """
    ✅ اجرای بکتست برای تمام symbols
    """
    from src.brain import TradingBrain
    from src.csv_store import BACKTEST_TRADES_CSV

    # پاکسازی فایل قبلی
    if os.path.exists(BACKTEST_TRADES_CSV):
        try:
            os.remove(BACKTEST_TRADES_CSV)
            logger.info(f"پاک شد: {BACKTEST_TRADES_CSV}")
        except OSError as e:
            logger.warning(f"⚠️ حذف فایل قدیمی ممکن نشد: {e}")

    logger.info(f"\n{'='*70}")
    logger.info(f"🚀 شروع بکتست تمام symbols")
    logger.info(f"{'='*70}\n")

    brain = TradingBrain()
    all_params = _load_best_params()
    results = {}

    for symbol in getattr(config, 'WATCHLIST', []):
        safe_name = symbol.replace('/', '_')
        csv_path = os.path.join(BASE_DIR, 'data', '4h', f"{safe_name}_history.csv")

        if not os.path.exists(csv_path):
            logger.warning(f"⚠️ فایل دیتای {symbol} یافت نشد: {csv_path}")
            continue

        try:
            df_raw = pd.read_csv(csv_path)
            logger.info(f"📊 لود: {symbol} - {len(df_raw)} ردیف")
        except Exception as e:
            logger.error(f"❌ خطا در خواندن {symbol}: {e}")
            continue

        params = all_params.get(symbol, {})
        results[symbol] = run_backtest(df_raw, symbol, params, model=brain)

    flush_closed_trades()
    export_to_sqlite()

    logger.info(f"\n{'='*70}")
    logger.info(f"✅ بکتست تمام شد")
    logger.info(f"تعداد symbols: {len(results)}")
    logger.info(f"{'='*70}\n")

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    )
    run_all_backtests()

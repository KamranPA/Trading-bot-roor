# FILE PATH: src/optimizer.py (v10.5 - Robustness fixes, unified with backtester)
# تغییرات نسبت به v10.4:
#   ✅ FIX: evaluate_parameters حالا حداقل طول داده (۲۱۰ ردیف) را چک می‌کند —
#      دقیقاً همان آستانه‌ای که backtester.py استفاده می‌کند. قبلاً optimizer
#      می‌توانست روی داده‌ی کوتاه (که ema_200/Trend_line در آن هنوز converge
#      نشده) بهینه‌سازی کند، در حالی‌که بک‌تست رسمی همان داده را رد می‌کرد.
#   ✅ FIX: حداقل تعداد معامله (MIN_TRADES_FOR_SELECTION) برای انتخاب یک
#      ترکیب پارامتر — از انتخاب ترکیب‌هایی با ۱-۲ معامله‌ی شانسی به‌عنوان
#      "بهترین پارامتر" جلوگیری می‌کند (ریسک overfit به نویز کوتاه‌مدت).
#   ✅ FIX: SL_RATIO حالا واقعاً در grid search جست‌وجو می‌شود (قبلاً همیشه
#      ثابت روی 1.0 پاس داده می‌شد، بدون این‌که کسی این را عمداً بخواهد).
#      برای اجرای زنده (mode="live", هر ۵۰ معامله) grid سبک‌تر نگه داشته
#      شده تا در بودجه‌ی زمانی GitHub Actions بگنجد؛ برای اجرای دستی/ماهانه
#      (mode="backtest") grid کامل‌تر اجرا می‌شود.
#   ✅ FIX: قبل از نوشتن best_params.json، اگر هیچ ارزی واقعاً پردازش نشده
#      باشد (مثلاً چون data/4h خالی بود)، فایل موجود دست‌نخورده می‌ماند —
#      از پاک‌شدن پارامترهای بهینه‌ی قبلی به‌خاطر نبود داده جلوگیری می‌کند.

import os
import sys
import json
import datetime
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from src import strategy_utils
from src.indicators import TechnicalIndicators
from src.brain import TradingBrain
from src.volume_filter import passes_volume_filter, VOLUME_MULTIPLIER
from src.ai_threshold import get_ai_threshold

# ✅ همان فلگ strategy.py/backtester.py — هماهنگ نگه می‌دارد که optimizer هم
# دقیقاً همان معیار پذیرش سیگنال لایو را برای ارزیابی پارامترها استفاده کند.
AI_GATE_ENABLED = bool(getattr(config, 'AI_GATE_ENABLED', True))

# ✅ FIX: هماهنگ با backtester.py — قبل از این تعداد ردیف، ema_200/Trend_line
# هنوز converge نشده و ارزیابی روی آن گمراه‌کننده است.
MIN_ROWS_FOR_EVALUATION = 210

# ✅ FIX: حداقل تعداد معامله‌ی لازم در بازه‌ی ارزیابی تا یک ترکیب پارامتر
# اصلاً واجد شرایط انتخاب به‌عنوان "بهترین" شود.
MIN_TRADES_FOR_SELECTION = 10


# ─── توابع کمکی مشترک ────────────────────────────────────────────────────────

def _to_brain_symbol(symbol: str) -> str:
    """BTCUSDT → BTC/USDT برای brain.py — یکسان با backtester.py"""
    if '/' not in symbol and 'USDT' in symbol:
        base = symbol.replace('USDT', '')
        return f"{base}/USDT"
    return symbol


_passes_volume_filter = passes_volume_filter


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    for col in df.columns:
        lower = col.lower()
        if lower in ('open', 'high', 'low', 'close', 'volume', 'timestamp'):
            col_map[col] = lower
    if col_map:
        df = df.rename(columns=col_map)
    df = df.loc[:, ~df.columns.duplicated(keep='first')]
    return df


def _add_uppercase_aliases(df: pd.DataFrame) -> pd.DataFrame:
    for lower, upper in [('high','High'),('low','Low'),('open','Open'),
                          ('close','Close'),('volume','Volume')]:
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


# ─── evaluate_parameters ─────────────────────────────────────────────────────

def evaluate_parameters(symbol, df, adx_th, swing_w, tp_r, sl_r, brain=None):
    """
    ارزیابی پارامترها روی ۲۰٪ آخر داده (validation set).
    رفتار کاملاً یکسان با backtester.py و strategy.py.

    Returns:
        (total_pnl, total_trades)
    """
    # ✅ FIX: حداقل طول داده — هماهنگ با backtester.py
    if df is None or len(df) < MIN_ROWS_FOR_EVALUATION:
        return 0.0, 0

    df_copy = _normalize_columns(df.copy())
    df_copy = _add_uppercase_aliases(df_copy)

    if brain is None:
        brain = TradingBrain()

    brain_symbol  = _to_brain_symbol(symbol)
    min_score     = float(getattr(config, 'MIN_REQUIRED_SCORE', 65))

    # ✅ AI_THRESHOLD per-symbol — یکسان با backtester.py/strategy.py
    _default_ai_th = float(getattr(config, 'AI_THRESHOLD', 65.0))
    ai_threshold    = get_ai_threshold(symbol, default=_default_ai_th)

    max_sl_pct    = float(getattr(config, 'MAX_SL_PERCENT',      0.05))
    max_open      = int(getattr(config,   'MAX_OPEN_POSITIONS',  999))
    w_ai  = float(getattr(config, 'WEIGHT_AI',  40))
    w_adx = float(getattr(config, 'WEIGHT_ADX', 20))
    w_rsi = float(getattr(config, 'WEIGHT_RSI', 20))
    w_ema = float(getattr(config, 'WEIGHT_EMA', 20))

    split_idx   = int(len(df_copy) * 0.8)
    open_trades = []
    total_pnl   = 0.0
    total_trades = 0

    for i in range(split_idx, len(df_copy)):
        row         = df_copy.iloc[i]
        high_price  = float(row.get('high',  0))
        low_price   = float(row.get('low',   0))
        close_price = float(row.get('close', 0))

        if high_price == 0 or low_price == 0 or close_price == 0:
            continue

        # ── بستن معاملات باز ────────────────────────────────────────────────
        still_open = []
        for trade in open_trades:
            d   = trade['direction']
            sl  = trade['stop_loss']
            tp2 = trade['tp2']
            ep  = trade['entry_price']
            closed = False; pnl = 0.0

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
                total_pnl    += pnl
                total_trades += 1
            else:
                still_open.append(trade)
        open_trades = still_open

        # ── فیلتر حجم per-candle ────────────────────────────────────────────
        if not _passes_volume_filter(row, symbol):
            continue

        # ── score ها ────────────────────────────────────────────────────────
        current_adx  = float(row.get('feat_adx',           row.get('ADX',  0)))
        current_rsi  = float(row.get('feat_rsi',           row.get('RSI',  50)))
        rsi_momentum = float(row.get('feat_rsi_momentum',  row.get('RSI_momentum', 0)))
        dev_val      = abs(float(row.get('feat_ema_deviation', row.get('EMA_diff', 0))))
        atr_pct      = float(row.get('feat_atr_percent',   0))
        trend_line   = float(row.get('feat_trend_line',    row.get('Trend_line', 0)))
        body_ratio   = float(row.get('feat_body_ratio',    row.get('Body_ratio', 0)))

        atr_val = _get_atr(row, close_price)

        adx_score = (min(100.0, 50.0 + (current_adx - adx_th) * 2.5)
                     if current_adx >= adx_th
                     else max(0.0, (current_adx / (adx_th + 1e-10)) * 50.0))

        rsi_score = (min(100.0, max(0.0, 50.0 + rsi_momentum * 5))
                     if current_rsi > 50
                     else min(100.0, max(0.0, 50.0 + (-rsi_momentum) * 5)))

        ema_score = min(100.0, (dev_val / 5.0) * 100.0)

        # ── AI score ────────────────────────────────────────────────────────
        ai_score    = 50.0
        ai_approved = True
        w_ai_eff    = 0.0

        model_active = brain.has_model(brain_symbol)
        if model_active:
            try:
                raw = brain.predict_probability(brain_symbol, {
                    'feat_adx':           current_adx,
                    'feat_atr_percent':   atr_pct,
                    'feat_rsi':           current_rsi,
                    'feat_trend_line':    trend_line,
                    'feat_ema_deviation': dev_val,
                    'feat_rsi_momentum':  rsi_momentum,
                    'feat_body_ratio':    body_ratio,
                })
                if raw is not None:
                    ai_score    = float(raw) * 100.0 if float(raw) <= 1.0 else float(raw)
                    ai_approved = ai_score >= ai_threshold
                    w_ai_eff    = w_ai
            except Exception:
                ai_approved = False

        w_sum_eff   = (w_ai_eff + w_adx + w_rsi + w_ema) or 100.0
        total_score = (
            ai_score * w_ai_eff +
            adx_score * w_adx +
            rsi_score * w_rsi +
            ema_score * w_ema
        ) / w_sum_eff

        if total_score < min_score or (AI_GATE_ENABLED and not ai_approved):
            continue

        if len(open_trades) >= max_open:
            continue

        df_slice        = df_copy.iloc[:i + 1]
        last_swing_high = strategy_utils.find_last_swing(df_slice, 'high', swing_w)
        last_swing_low  = strategy_utils.find_last_swing(df_slice, 'low',  swing_w)

        if last_swing_high is None or last_swing_low is None:
            continue

        sl_dist = min(1.5 * atr_val * sl_r, close_price * max_sl_pct)
        if sl_dist <= 0:
            continue

        trade_id = f"{symbol}_{i}"

        if high_price > last_swing_high and current_rsi > 50:
            open_trades.append({
                'id': trade_id, 'direction': 'LONG',
                'entry_price': close_price,
                'stop_loss':   close_price - sl_dist,
                'tp2':         close_price + sl_dist * tp_r,
            })
        elif low_price < last_swing_low and current_rsi < 50:
            open_trades.append({
                'id': trade_id, 'direction': 'SHORT',
                'entry_price': close_price,
                'stop_loss':   close_price + sl_dist,
                'tp2':         close_price - sl_dist * tp_r,
            })

    # ── بستن معاملات باقی‌مانده با قیمت آخر ────────────────────────────────
    last_price = float(df_copy.iloc[-1]['close'])
    for trade in open_trades:
        ep = trade['entry_price']
        d  = trade['direction']
        pnl = ((last_price - ep) / ep * 100
               if d == 'LONG'
               else (ep - last_price) / ep * 100)
        total_pnl    += pnl
        total_trades += 1

    return total_pnl, total_trades


# ─── optimize_all ─────────────────────────────────────────────────────────────

def optimize_all(mode="backtest"):
    """
    mode="live":     grid سبک‌تر (اجرا هر ۵۰ معامله داخل trade.yml، بودجه‌ی
                      زمانی محدودتر) — SL_RATIO ثابت روی مقدار config.
    mode="backtest": grid کامل‌تر (اجرای دستی backtest.yml یا Monthly Retrain)
                      — SL_RATIO هم واقعاً جست‌وجو می‌شود.
    """
    print(f"شروع بهینه‌سازی کامل پارامترها (mode={mode})...")
    params_file = os.path.join(BASE_DIR, "best_params.json")

    adx_options   = [15, 20, 25]
    swing_options = [3, 5, 7]
    tp_options    = [1.5, 2.0, 2.5]

    if mode == "live":
        # ✅ سبک‌تر برای اجرای زنده — همان اندازه‌ی grid قبلی (۲۷ ترکیب)
        sl_options = [float(getattr(config, 'SL_RATIO', 1.0))]
    else:
        # ✅ FIX: SL_RATIO واقعاً جست‌وجو می‌شود (۸۱ ترکیب) — فقط در اجرای
        # دستی/ماهانه که بودجه‌ی زمانی بیشتری دارد.
        sl_options = [0.8, 1.0, 1.2]

    brain = TradingBrain()
    best_params_dict = {}
    processed_symbols = []

    for symbol in config.WATCHLIST:
        safe_name = symbol.replace('/', '_')
        file_path = os.path.join(BASE_DIR, "data", "4h", f"{safe_name}_history.csv")

        if not os.path.exists(file_path):
            print(f"فایل CSV برای {symbol} پیدا نشد - skip")
            continue

        try:
            df_raw = pd.read_csv(file_path)
        except Exception as e:
            print(f"❌ خطا در خواندن {symbol}: {e}")
            continue

        df_raw = _normalize_columns(df_raw)

        # ✅ FIX: چک طول داده قبل از هر محاسبه‌ی سنگین
        if len(df_raw) < MIN_ROWS_FOR_EVALUATION:
            print(f"⚠️ {symbol}: داده ناکافی ({len(df_raw)} < {MIN_ROWS_FOR_EVALUATION} ردیف) - skip")
            continue

        df, meta = TechnicalIndicators.calculate_all_features(df_raw, symbol=symbol)
        if not meta.get('success', False):
            print(f"محاسبه اندیکاتورها برای {symbol} ناموفق - skip")
            continue

        df = _normalize_columns(df)
        df = _add_uppercase_aliases(df)

        best_pnl = -9999.0
        best_trades = 0
        # پیش‌فرض: پارامترهای فعلی config — اگر هیچ ترکیبی حداقل تعداد
        # معامله را نداشته باشد، همین fallback امن باقی می‌ماند.
        best_cfg = {
            "ADX_THRESHOLD": config.ADX_THRESHOLD,
            "SWING_WINDOW":  config.SWING_WINDOW,
            "TP_RATIO":      config.TP_RATIO,
            "SL_RATIO":      float(getattr(config, 'SL_RATIO', 1.0)),
        }
        found_valid_combo = False

        for adx in adx_options:
            for sw in swing_options:
                for tp in tp_options:
                    for sl in sl_options:
                        pnl, trades = evaluate_parameters(
                            symbol, df, adx, sw, tp, sl, brain=brain
                        )
                        # ✅ FIX: ترکیبی که به حداقل تعداد معامله نرسیده
                        # واجد شرایط انتخاب نیست (جلوگیری از overfit به نویز)
                        if trades < MIN_TRADES_FOR_SELECTION:
                            continue
                        if pnl > best_pnl:
                            best_pnl = pnl
                            best_trades = trades
                            found_valid_combo = True
                            best_cfg = {
                                "ADX_THRESHOLD": adx,
                                "SWING_WINDOW":  sw,
                                "TP_RATIO":      tp,
                                "SL_RATIO":      sl,
                            }

        best_params_dict[symbol] = best_cfg
        processed_symbols.append(symbol)

        if found_valid_combo:
            print(
                f"{symbol}: ADX={best_cfg['ADX_THRESHOLD']} "
                f"SW={best_cfg['SWING_WINDOW']} "
                f"TP={best_cfg['TP_RATIO']} "
                f"SL={best_cfg['SL_RATIO']} | "
                f"PnL={best_pnl:.2f}% | trades={best_trades}"
            )
        else:
            print(
                f"⚠️ {symbol}: هیچ ترکیبی به حداقل {MIN_TRADES_FOR_SELECTION} معامله نرسید "
                f"— پارامترهای پیش‌فرض config نگه داشته شد"
            )

    # ✅ FIX: اگر هیچ ارزی واقعاً پردازش نشد (مثلاً data/4h خالی بود)،
    # فایل best_params.json موجود دست‌نخورده باقی می‌ماند — از پاک‌شدن
    # پارامترهای بهینه‌ی قبلی به‌خاطر نبود داده جلوگیری می‌شود.
    if not processed_symbols:
        print("⚠️ هیچ ارزی پردازش نشد (داده‌ی موجود در data/4h کافی نیست) — "
              "best_params.json دست‌نخورده باقی می‌ماند.")
        if os.path.exists(params_file):
            with open(params_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    best_params_dict['_updated_at'] = datetime.datetime.utcnow().isoformat()

    with open(params_file, "w") as f:
        json.dump(best_params_dict, f, indent=4)

    print(f"✅ best_params.json آپدیت شد ({len(processed_symbols)} ارز پردازش شد).")
    return best_params_dict


if __name__ == "__main__":
    optimize_all()

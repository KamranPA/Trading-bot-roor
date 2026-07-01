"""
FILE PATH: src/train_model.py (v12.0 - Per-symbol AI_THRESHOLD calibration)
تغییرات نسبت به v11.0:
  ✅ بعد از training هر مدل، روی X_test احتمال پیش‌بینی می‌شود
  ✅ AI_THRESHOLD پیشنهادی per-symbol از روی percentile توزیع امتیازها محاسبه می‌شود
  ✅ ai_thresholds.json در ریشه پروژه ذخیره می‌شود (کلید: برند symbol مثل BTC/USDT)
  ✅ AI_THRESHOLD_PERCENTILE از config قابل تنظیم (پیش‌فرض 60)
"""

import pandas as pd
import numpy as np
import pickle
import logging
import argparse
import os
import sys
import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
try:
    from src.volume_filter import apply_volume_filter_df
except ImportError:
    try:
        from volume_filter import apply_volume_filter_df
    except ImportError:
        apply_volume_filter_df = None

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    logging.warning("LightGBM نصب نیست! pip install lightgbm")

try:
    from indicators import TechnicalIndicators
    HAS_INDICATORS = True
except ImportError:
    try:
        from src.indicators import TechnicalIndicators
        HAS_INDICATORS = True
    except ImportError:
        HAS_INDICATORS = False

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ─── فیچرها: ۸ فیچر ───────────────────────────────────────────────────────────
FEAT_COLUMNS = [
    'feat_adx',
    'feat_atr_percent',
    'feat_rsi',
    'feat_trend_line',
    'feat_ema_deviation',
    'feat_rsi_momentum',
    'feat_body_ratio',
    'feat_volume_ratio',
]

MIN_TRAINING_SAMPLES = 50
TARGET_LOOKAHEAD = 20

# ✅ صدکی که برای AI_THRESHOLD پیشنهادی استفاده می‌شود.
# مثال: 60 یعنی فقط 40% بهترین امتیازهای مدل از فیلتر عبور می‌کنند.
AI_THRESHOLD_PERCENTILE = float(getattr(config, 'AI_THRESHOLD_PERCENTILE', 60))

# حد پایین/بالای منطقی برای جلوگیری از threshold های افراطی
AI_THRESHOLD_MIN = float(getattr(config, 'AI_THRESHOLD_MIN', 20.0))
AI_THRESHOLD_MAX = float(getattr(config, 'AI_THRESHOLD_MAX', 80.0))

AI_THRESHOLDS_FILE = os.path.join(BASE_DIR, 'ai_thresholds.json')


# ─── تابع target (بدون تغییر نسبت به v11.0) ──────────────────────────────────

def _build_target(
    df: pd.DataFrame,
    symbol: str,
    tp_ratio: Optional[float] = None,
    sl_ratio: Optional[float] = None,
) -> pd.Series:
    """
    ✅ tp_ratio/sl_ratio اگر پاس داده نشوند، از config ثابت خوانده می‌شوند.
    توصیه می‌شود از _get_symbol_tp_sl() مقدار اختصاصی هر symbol
    (از best_params.json) پاس داده شود تا target با پارامترهای واقعی
    معامله‌ی همان ارز هماهنگ باشد — نه یک TP_RATIO ثابت سراسری.
    """
    if sl_ratio is None:
        sl_ratio = float(getattr(config, 'SL_RATIO',  1.0))
    if tp_ratio is None:
        tp_ratio = float(getattr(config, 'TP_RATIO',  2.0))
    max_sl = float(getattr(config, 'MAX_SL_PERCENT', 0.05))

    close  = df['close'].values
    high   = df['high'].values
    low    = df['low'].values
    atr    = df['atr'].values if 'atr' in df.columns else df.get('ATR', pd.Series(np.zeros(len(df)))).values
    rsi    = df['feat_rsi'].values if 'feat_rsi' in df.columns else np.full(len(df), 50.0)

    n      = len(df)
    target = np.full(n, np.nan)

    for i in range(n - TARGET_LOOKAHEAD):
        entry = close[i]
        if entry == 0:
            continue

        atr_val = float(atr[i]) if atr[i] > 1.0 else entry * 0.01
        sl_dist = min(1.5 * atr_val * sl_ratio, entry * max_sl)
        if sl_dist <= 0:
            continue

        cur_rsi = float(rsi[i])

        if cur_rsi > 52:
            sl_price  = entry - sl_dist
            tp_price  = entry + sl_dist * tp_ratio
            direction = 'LONG'
        elif cur_rsi < 48:
            sl_price  = entry + sl_dist
            tp_price  = entry - sl_dist * tp_ratio
            direction = 'SHORT'
        else:
            continue

        hit_tp = False
        hit_sl = False

        for j in range(i + 1, min(i + TARGET_LOOKAHEAD + 1, n)):
            h = float(high[j])
            l = float(low[j])

            if direction == 'LONG':
                if l <= sl_price:
                    hit_sl = True; break
                if h >= tp_price:
                    hit_tp = True; break
            else:
                if h >= sl_price:
                    hit_sl = True; break
                if l <= tp_price:
                    hit_tp = True; break

        target[i] = 1 if hit_tp else 0

    result = pd.Series(target, index=df.index, name='target')
    tp_count = int((result == 1).sum())
    sl_count = int((result == 0).sum())
    if tp_count + sl_count > 0:
        logger.info(
            f"  target: TP={tp_count} ({tp_count/(tp_count+sl_count)*100:.1f}%) "
            f"SL/timeout={sl_count} ({sl_count/(tp_count+sl_count)*100:.1f}%) "
            f"(از {n} کندل)"
        )
    return result


def _apply_volume_filter(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if apply_volume_filter_df is not None:
        return apply_volume_filter_df(df, symbol)
    return df


def _load_best_params() -> Dict:
    """
    خواندن best_params.json (خروجی optimizer.py).
    اگر فایل موجود نباشد یا خراب باشد، dict خالی برمی‌گرداند (fallback به config).
    """
    path = os.path.join(BASE_DIR, 'best_params.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ خطا در خواندن best_params.json: {e}")
        return {}


def _get_symbol_tp_sl(symbol: str, best_params: Dict) -> Tuple[float, float]:
    """
    خواندن TP_RATIO/SL_RATIO اختصاصی هر ارز از best_params.json (خروجی optimizer.py).
    اولویت: best_params[symbol] > config ثابت.
    این تضمین می‌کند هدف training (target) با همان نسبت TP/SL که در بکتست/لایو
    برای این ارز استفاده می‌شود هماهنگ باشد — نه یک TP_RATIO ثابت سراسری.
    """
    entry = best_params.get(symbol, {})
    tp_ratio = float(entry.get('TP_RATIO', getattr(config, 'TP_RATIO', 2.0)))
    sl_ratio = float(entry.get('SL_RATIO', getattr(config, 'SL_RATIO', 1.0)))
    return tp_ratio, sl_ratio


def _model_key(symbol: str) -> str:
    """
    BTCUSDT → BTC/USDT → BTC_USDT  (نام فایل مدل، سازگار با brain.py)
    """
    if '/' not in symbol and 'USDT' in symbol:
        base   = symbol.replace('USDT', '')
        symbol = f"{base}/USDT"
    return symbol.replace('/', '_')


def _brain_symbol(symbol: str) -> str:
    """
    BTCUSDT → BTC/USDT  (کلیدی که brain.py و backtester.py برای جستجو استفاده می‌کنند)
    """
    if '/' not in symbol and 'USDT' in symbol:
        base = symbol.replace('USDT', '')
        return f"{base}/USDT"
    return symbol


# ─── ModelTrainer ─────────────────────────────────────────────────────────────

class ModelTrainer:

    def __init__(self, model_dir: str = "./models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        # نگاشت brain_symbol → ai_threshold پیشنهادی
        self.ai_thresholds: Dict[str, Dict] = {}

    def train_multiple_symbols(
        self,
        data_dict: Dict[str, pd.DataFrame],
    ) -> Dict:

        results = {
            'timestamp':  datetime.now().isoformat(),
            'model_type': 'LightGBM',
            'features':   FEAT_COLUMNS,
            'target':     f'SL/TP simulation (lookahead={TARGET_LOOKAHEAD} candles)',
            'ai_threshold_percentile': AI_THRESHOLD_PERCENTILE,
            'symbols':    {},
            'summary':    {'total': len(data_dict), 'successful': 0, 'failed': 0}
        }

        logger.info(f"شروع training برای {len(data_dict)} symbol")
        logger.info(f"فیچرها ({len(FEAT_COLUMNS)}): {FEAT_COLUMNS}")
        logger.info(f"AI_THRESHOLD percentile: {AI_THRESHOLD_PERCENTILE}")
        logger.info("=" * 65)

        # ✅ خواندن best_params.json یک‌بار (خروجی optimizer.py)
        # تا target هر symbol با TP_RATIO/SL_RATIO اختصاصی همان ارز ساخته شود
        best_params = _load_best_params()
        if best_params:
            logger.info(f"✅ best_params.json یافت شد — {len([k for k in best_params if not k.startswith('_')])} ارز کالیبره‌شده")
        else:
            logger.info("ℹ️ best_params.json یافت نشد — از config.TP_RATIO/SL_RATIO ثابت استفاده می‌شود")

        for symbol, df in data_dict.items():
            logger.info(f"\nپردازش: {symbol}")

            # ── ۱. اندیکاتورها ────────────────────────────────────────────
            if HAS_INDICATORS:
                df_feat, meta = TechnicalIndicators.calculate_all_features(
                    df, symbol=symbol, min_rows_required=100
                )
                if not meta.get('success', False):
                    logger.error(f"  اندیکاتورها ناموفق: {meta.get('missing_features')}")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'indicators failed'}
                    results['summary']['failed'] += 1
                    continue
            else:
                df_feat = df.copy()

            # ── ۲. فیلتر حجم ─────────────────────────────────────────────
            df_feat = _apply_volume_filter(df_feat, symbol)

            # ── ۳. target (با TP_RATIO/SL_RATIO اختصاصی این symbol) ───────
            sym_tp_ratio, sym_sl_ratio = _get_symbol_tp_sl(symbol, best_params)
            logger.info(f"  TP_RATIO={sym_tp_ratio} SL_RATIO={sym_sl_ratio} (برای ساخت target)")
            df_feat['target'] = _build_target(
                df_feat, symbol,
                tp_ratio=sym_tp_ratio,
                sl_ratio=sym_sl_ratio,
            )

            # ── ۴. بررسی فیچرها ──────────────────────────────────────────
            missing = [f for f in FEAT_COLUMNS if f not in df_feat.columns]
            if missing:
                logger.error(f"  فیچرهای گمشده: {missing}")
                results['symbols'][symbol] = {'status': 'FAILED', 'reason': f'missing: {missing}'}
                results['summary']['failed'] += 1
                continue

            try:
                X = df_feat[FEAT_COLUMNS].copy()
                y = df_feat['target'].copy()

                valid = X.notna().all(axis=1) & y.notna()
                X, y  = X[valid], y[valid]

                if len(X) < MIN_TRAINING_SAMPLES:
                    logger.error(f"  نمونه ناکافی: {len(X)} < {MIN_TRAINING_SAMPLES}")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'insufficient samples'}
                    results['summary']['failed'] += 1
                    continue

                tp_pct = float((y == 1).mean() * 100)
                logger.info(f"  {len(X)} نمونه | TP={tp_pct:.1f}% | SL={100-tp_pct:.1f}%")

                split  = int(len(X) * 0.8)
                X_train, X_test = X.iloc[:split], X.iloc[split:]
                y_train, y_test = y.iloc[:split], y.iloc[split:]

                logger.info(f"  train={len(X_train)} | test={len(X_test)}")

                if not HAS_LIGHTGBM:
                    logger.error("  LightGBM نصب نیست!")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'lightgbm not installed'}
                    results['summary']['failed'] += 1
                    continue

                n_neg = int((y_train == 0).sum())
                n_pos = int((y_train == 1).sum())
                scale = n_neg / max(n_pos, 1)

                model = lgb.LGBMClassifier(
                    n_estimators=300,
                    max_depth=6,
                    learning_rate=0.03,
                    num_leaves=31,
                    min_child_samples=20,
                    scale_pos_weight=scale,
                    random_state=42,
                    n_jobs=-1,
                    verbose=-1,
                )

                model.fit(
                    X_train, y_train,
                    eval_set=[(X_test, y_test)],
                    callbacks=[
                        lgb.early_stopping(30, verbose=False),
                        lgb.log_evaluation(0),
                    ]
                )

                train_score = float(model.score(X_train, y_train))
                test_score  = float(model.score(X_test,  y_test))
                logger.info(f"  Train accuracy={train_score:.4f} | Test accuracy={test_score:.4f}")

                importances = dict(zip(FEAT_COLUMNS, model.feature_importances_))
                top = sorted(importances.items(), key=lambda x: -x[1])[:3]
                logger.info(f"  Top features: {[(k, int(v)) for k,v in top]}")

                # ── ✅ کالیبراسیون AI_THRESHOLD per-symbol ─────────────────
                # روی X_test (داده‌ای که مدل آن را در training ندیده) احتمال می‌گیریم
                # و یک صدک از توزیع را به‌عنوان threshold پیشنهادی انتخاب می‌کنیم.
                proba_test = model.predict_proba(X_test)[:, 1] * 100.0  # 0..100

                if len(proba_test) > 0:
                    suggested_threshold = float(np.percentile(proba_test, AI_THRESHOLD_PERCENTILE))
                    suggested_threshold = max(AI_THRESHOLD_MIN, min(AI_THRESHOLD_MAX, suggested_threshold))
                else:
                    suggested_threshold = float(getattr(config, 'AI_THRESHOLD', 65.0))

                score_stats = {
                    'min':    round(float(np.min(proba_test)), 2) if len(proba_test) else None,
                    'p25':    round(float(np.percentile(proba_test, 25)), 2) if len(proba_test) else None,
                    'median': round(float(np.median(proba_test)), 2) if len(proba_test) else None,
                    'p75':    round(float(np.percentile(proba_test, 75)), 2) if len(proba_test) else None,
                    'max':    round(float(np.max(proba_test)), 2) if len(proba_test) else None,
                }

                logger.info(
                    f"  📊 توزیع امتیاز AI روی test: "
                    f"min={score_stats['min']} p25={score_stats['p25']} "
                    f"median={score_stats['median']} p75={score_stats['p75']} max={score_stats['max']}"
                )
                logger.info(
                    f"  🎯 AI_THRESHOLD پیشنهادی (صدک {AI_THRESHOLD_PERCENTILE}): "
                    f"{suggested_threshold:.2f}"
                )

                brain_sym = _brain_symbol(symbol)
                self.ai_thresholds[brain_sym] = {
                    'threshold':   round(suggested_threshold, 2),
                    'percentile':  AI_THRESHOLD_PERCENTILE,
                    'score_stats': score_stats,
                    'test_samples': len(proba_test),
                    'updated_at':  datetime.now().isoformat(),
                }

                # ── ذخیره مدل ────────────────────────────────────────────
                safe_name  = _model_key(symbol)
                model_path = self.model_dir / f"{safe_name}_model.pkl"

                with open(model_path, 'wb') as f:
                    pickle.dump(model, f)

                logger.info(f"  ✅ ذخیره شد: {model_path}  (brain key: '{brain_sym}')")

                results['symbols'][symbol] = {
                    'status':           'SUCCESS',
                    'model_path':       str(model_path),
                    'brain_key':        brain_sym,
                    'train_score':      train_score,
                    'test_score':       test_score,
                    'samples':          len(X),
                    'tp_percent':       round(tp_pct, 1),
                    'top_features':     top,
                    'ai_threshold':     round(suggested_threshold, 2),
                    'score_stats':      score_stats,
                    # ✅ ثبت پارامترهایی که برای ساخت target استفاده شدند —
                    # برای شفافیت/دیباگ که target با کدام TP_RATIO/SL_RATIO هماهنگ شده
                    'target_tp_ratio':  sym_tp_ratio,
                    'target_sl_ratio':  sym_sl_ratio,
                }
                results['summary']['successful'] += 1

            except Exception as e:
                logger.error(f"  خطا: {e}", exc_info=True)
                results['symbols'][symbol] = {'status': 'FAILED', 'reason': str(e)}
                results['summary']['failed'] += 1

        logger.info("\n" + "=" * 65)
        logger.info(
            f"نتیجه نهایی: {results['summary']['successful']} موفق, "
            f"{results['summary']['failed']} ناموفق"
        )
        return results

    def save_results(self, results: Dict, path: str = "training_results.json"):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"نتایج ذخیره شد: {path}")

    def save_ai_thresholds(self, path: str = None):
        """
        ذخیره ai_thresholds.json — کلید: برند symbol (مثل 'BTC/USDT')
        این فایل توسط backtester.py / optimizer.py / strategy.py (لایو) خوانده می‌شود
        تا به‌جای config.AI_THRESHOLD ثابت، از مقدار per-symbol استفاده شود.
        """
        if path is None:
            path = AI_THRESHOLDS_FILE

        existing = {}
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except Exception:
                existing = {}

        existing.update(self.ai_thresholds)
        existing['_updated_at'] = datetime.now().isoformat()
        existing['_percentile'] = AI_THRESHOLD_PERCENTILE

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"✅ ai_thresholds.json ذخیره شد: {path}")
        for sym, info in self.ai_thresholds.items():
            logger.info(f"   {sym}: threshold={info['threshold']}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--monthly', action='store_true')
    args = parser.parse_args()

    logger.info("شروع pipeline آموزش LightGBM v12.0 (با کالیبراسیون per-symbol)")
    logger.info(f"فیچرها: {FEAT_COLUMNS}")

    data_dir = os.path.join(BASE_DIR, "data", "4h")
    data_dict = {}

    for symbol in config.WATCHLIST:
        safe_name = symbol.replace("/", "_")
        filepath  = os.path.join(data_dir, f"{safe_name}_history.csv")

        if not os.path.exists(filepath):
            logger.warning(f"فایل یافت نشد: {filepath}")
            continue

        try:
            df = pd.read_csv(filepath)

            col_map = {
                'Timestamp': 'timestamp', 'Open':  'open',
                'High':      'high',      'Low':   'low',
                'Close':     'close',     'Volume':'volume',
            }
            df.rename(columns={k: v for k, v in col_map.items() if k in df.columns},
                      inplace=True)

            data_dict[symbol] = df
            logger.info(f"لود شد: {symbol} — {len(df)} ردیف")

        except Exception as e:
            logger.error(f"خطا در لود {symbol}: {e}")

    if not data_dict:
        logger.error("هیچ داده‌ای لود نشد!")
        sys.exit(1)

    logger.info(f"\n{len(data_dict)} ارز آماده: {list(data_dict.keys())}")

    model_dir = os.path.join(BASE_DIR, "src", "models")
    trainer   = ModelTrainer(model_dir=model_dir)
    results   = trainer.train_multiple_symbols(data_dict)

    trainer.save_results(results, os.path.join(BASE_DIR, "training_results.json"))
    trainer.save_ai_thresholds()   # ✅ ذخیره ai_thresholds.json

    if results['summary']['successful'] == 0:
        logger.error("هیچ مدلی ذخیره نشد!")
        sys.exit(1)

    logger.info("✅ Pipeline با موفقیت تمام شد.")
    sys.exit(0)

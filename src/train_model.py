"""
FILE PATH: src/train_model.py (v13.0 - Root-cause fix for weak/flat model output)
تغییرات نسبت به v12.1:

  🔴 ریشه‌ی اصلی ضعف مدل (بازه‌ی احتمال خروجی فقط ۲-۳ واحد روی صدها نمونه):
     eval_set برای early_stopping دقیقاً همان X_test/y_test بود که بعداً هم
     برای گزارش test_score و هم برای کالیبراسیون AI_THRESHOLD استفاده می‌شد.
     چون برچسب TP/SL روی این افق (۲۰ کندل ۴ساعته) نویزی است، loss روی این
     validation تقریباً بلافاصله ثابت می‌ماند و early_stopping خیلی زود
     (شاید ۵-۱۵ درخت از ۳۰۰ درخت مجاز) فعال می‌شود → مدل فرصت نمی‌کند فضای
     احتمال را باز کند → خروجی تقریباً ثابت برای همه‌ی کندل‌ها.

  ✅ FIX 1: حالا سه‌بخشی (train/valid/test) — early stopping روی valid
     انجام می‌شود، نه روی test. test فقط برای گزارش نهایی و کالیبراسیون
     استفاده می‌شود و در تصمیم "چند درخت بساز" هیچ نقشی ندارد.
  ✅ FIX 2: warm-up ۲۰۰ ردیفی هماهنگ با backtester.py — قبل از این تعداد
     ردیف، ema_200/Trend_line هنوز converge نشده و فیچر feat_trend_line
     نامعتبر است؛ این ردیف‌ها دیگر وارد training نمی‌شوند.
  ✅ FIX 3: آستانه‌ی RSI برای ساخت target از (>52 / <48) به (>50 / <50)
     تغییر کرد — دقیقاً همان آستانه‌ای که strategy.py برای تعیین جهت
     استفاده می‌کند. قبلاً مدل هرگز روی کندل‌های RSI∈[48,52] آموزش
     نمی‌دید، ولی در لایو دقیقاً روی همان کندل‌ها هم پرسیده می‌شد.
  ✅ FIX 4: لاگ تشخیصی جدید — best_iteration_ (چند درخت واقعاً ساخته شد)،
     AUC و logloss دستی (بدون وابستگی به scikit-learn) روی test واقعی.
     این اعداد مشخص می‌کنند که آیا فیکس‌های بالا مشکل را حل کردند یا
     سیگنال قابل‌یادگیری در این فیچرها/برچسب اصلاً کم است (AUC≈0.5).
  ✅ FIX 5 (v13.1): patience از 30 به 75 افزایش یافت. با اجرای اول این
     نسخه دیده شد best_iteration_ بین ۱ تا ۸ بود — یعنی روی validation
     کوچک (~۱۵٪ داده)، نویز لاگ‌لاس باعث توقف خیلی زودهنگام می‌شد، حتی
     در حالی‌که AUC واقعی روی test (۰.۵۷-۰.۶۲) نشان می‌داد سیگنال ضعیف
     ولی واقعی وجود دارد. patience بالاتر فرصت بیشتری برای همگرایی می‌دهد.
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

TARGET_LOOKAHEAD = 20
WARMUP_ROWS = 200

TRAIN_FRAC = 0.70
VALID_FRAC = 0.15

MIN_TRAINING_SAMPLES = 150
MIN_VALID_SAMPLES    = 30
MIN_TEST_SAMPLES     = 30
MIN_TEST_SAMPLES_FOR_CALIBRATION = 30

AI_THRESHOLD_PERCENTILE = float(getattr(config, 'AI_THRESHOLD_PERCENTILE', 60))
AI_THRESHOLD_MIN = float(getattr(config, 'AI_THRESHOLD_MIN', 20.0))
AI_THRESHOLD_MAX = float(getattr(config, 'AI_THRESHOLD_MAX', 80.0))

AI_THRESHOLDS_FILE = os.path.join(BASE_DIR, 'ai_thresholds.json')


def _manual_log_loss(y_true, y_prob, eps: float = 1e-12) -> float:
    y_prob = np.clip(y_prob, eps, 1 - eps)
    return float(-np.mean(y_true * np.log(y_prob) + (1 - y_true) * np.log(1 - y_prob)))


def _manual_auc(y_true, y_score) -> Optional[float]:
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    n_pos = int((y_true == 1).sum())
    n_neg = int((y_true == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return None
    order = np.argsort(y_score, kind='mergesort')
    ranks = np.empty(len(y_score), dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1)
    sum_ranks_pos = ranks[y_true == 1].sum()
    auc = (sum_ranks_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(auc)


def _build_target(df, symbol, tp_ratio=None, sl_ratio=None):
    if sl_ratio is None:
        sl_ratio = float(getattr(config, 'SL_RATIO', 1.0))
    if tp_ratio is None:
        tp_ratio = float(getattr(config, 'TP_RATIO', 2.0))
    max_sl = float(getattr(config, 'MAX_SL_PERCENT', 0.05))

    close = df['close'].values
    high  = df['high'].values
    low   = df['low'].values
    atr   = df['atr'].values if 'atr' in df.columns else df.get('ATR', pd.Series(np.zeros(len(df)))).values
    rsi   = df['feat_rsi'].values if 'feat_rsi' in df.columns else np.full(len(df), 50.0)

    n = len(df)
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

        if cur_rsi > 50:
            sl_price = entry - sl_dist
            tp_price = entry + sl_dist * tp_ratio
            direction = 'LONG'
        elif cur_rsi < 50:
            sl_price = entry + sl_dist
            tp_price = entry - sl_dist * tp_ratio
            direction = 'SHORT'
        else:
            continue

        hit_tp = False
        hit_sl = False
        for j in range(i + 1, min(i + TARGET_LOOKAHEAD + 1, n)):
            h = float(high[j]); l = float(low[j])
            if direction == 'LONG':
                if l <= sl_price: hit_sl = True; break
                if h >= tp_price: hit_tp = True; break
            else:
                if h >= sl_price: hit_sl = True; break
                if l <= tp_price: hit_tp = True; break

        target[i] = 1 if hit_tp else 0

    result = pd.Series(target, index=df.index, name='target')
    tp_count = int((result == 1).sum())
    sl_count = int((result == 0).sum())
    if tp_count + sl_count > 0:
        logger.info(f"  target: TP={tp_count} ({tp_count/(tp_count+sl_count)*100:.1f}%) "
                    f"SL/timeout={sl_count} ({sl_count/(tp_count+sl_count)*100:.1f}%) (از {n} کندل)")
    return result


def _apply_volume_filter(df, symbol):
    if apply_volume_filter_df is not None:
        return apply_volume_filter_df(df, symbol)
    return df


def _load_best_params():
    path = os.path.join(BASE_DIR, 'best_params.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ خطا در خواندن best_params.json: {e}")
        return {}


def _get_symbol_tp_sl(symbol, best_params):
    entry = best_params.get(symbol, {})
    tp_ratio = float(entry.get('TP_RATIO', getattr(config, 'TP_RATIO', 2.0)))
    sl_ratio = float(entry.get('SL_RATIO', getattr(config, 'SL_RATIO', 1.0)))
    return tp_ratio, sl_ratio


def _model_key(symbol):
    if '/' not in symbol and 'USDT' in symbol:
        base = symbol.replace('USDT', '')
        symbol = f"{base}/USDT"
    return symbol.replace('/', '_')


def _brain_symbol(symbol):
    if '/' not in symbol and 'USDT' in symbol:
        base = symbol.replace('USDT', '')
        return f"{base}/USDT"
    return symbol


class ModelTrainer:

    def __init__(self, model_dir: str = "./models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.ai_thresholds: Dict[str, Dict] = {}

    def train_multiple_symbols(self, data_dict):
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
        logger.info(f"تقسیم داده: train={TRAIN_FRAC:.0%} / valid={VALID_FRAC:.0%} / "
                    f"test={1-TRAIN_FRAC-VALID_FRAC:.0%} (زمانی، بدون shuffle)")
        logger.info(f"warm-up: {WARMUP_ROWS} ردیف اول حذف می‌شود (هماهنگ با backtester.py)")
        logger.info("=" * 65)

        best_params = _load_best_params()
        if best_params:
            logger.info(f"✅ best_params.json یافت شد — {len([k for k in best_params if not k.startswith('_')])} ارز کالیبره‌شده")
        else:
            logger.info("ℹ️ best_params.json یافت نشد — از config.TP_RATIO/SL_RATIO ثابت استفاده می‌شود")

        for symbol, df in data_dict.items():
            logger.info(f"\nپردازش: {symbol}")

            if HAS_INDICATORS:
                df_feat, meta = TechnicalIndicators.calculate_all_features(df, symbol=symbol, min_rows_required=100)
                if not meta.get('success', False):
                    logger.error(f"  اندیکاتورها ناموفق: {meta.get('missing_features')}")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'indicators failed'}
                    results['summary']['failed'] += 1
                    continue
            else:
                df_feat = df.copy()

            sym_tp_ratio, sym_sl_ratio = _get_symbol_tp_sl(symbol, best_params)
            logger.info(f"  TP_RATIO={sym_tp_ratio} SL_RATIO={sym_sl_ratio} (برای ساخت target)")
            df_feat['target'] = _build_target(df_feat, symbol, tp_ratio=sym_tp_ratio, sl_ratio=sym_sl_ratio)

            if len(df_feat) > WARMUP_ROWS:
                df_feat = df_feat.iloc[WARMUP_ROWS:].reset_index(drop=True)
            else:
                logger.warning(f"  ⚠️ {symbol}: طول داده ({len(df_feat)}) کمتر از warm-up ({WARMUP_ROWS}) — رد شد")

            df_feat = _apply_volume_filter(df_feat, symbol)

            missing = [f for f in FEAT_COLUMNS if f not in df_feat.columns]
            if missing:
                logger.error(f"  فیچرهای گمشده: {missing}")
                results['symbols'][symbol] = {'status': 'FAILED', 'reason': f'missing: {missing}'}
                results['summary']['failed'] += 1
                continue

            try:
                X = df_feat[FEAT_COLUMNS].copy()
                y = df_feat['target'].copy()
                valid_mask = X.notna().all(axis=1) & y.notna()
                X, y = X[valid_mask], y[valid_mask]

                if len(X) < MIN_TRAINING_SAMPLES:
                    logger.error(f"  نمونه ناکافی: {len(X)} < {MIN_TRAINING_SAMPLES}")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'insufficient samples'}
                    results['summary']['failed'] += 1
                    continue

                tp_pct = float((y == 1).mean() * 100)
                logger.info(f"  {len(X)} نمونه (بعد از warm-up/فیلتر) | TP={tp_pct:.1f}% | SL={100-tp_pct:.1f}%")

                n = len(X)
                split_train = int(n * TRAIN_FRAC)
                split_valid = int(n * (TRAIN_FRAC + VALID_FRAC))
                X_train, y_train = X.iloc[:split_train], y.iloc[:split_train]
                X_valid, y_valid = X.iloc[split_train:split_valid], y.iloc[split_train:split_valid]
                X_test,  y_test  = X.iloc[split_valid:], y.iloc[split_valid:]

                logger.info(f"  train={len(X_train)} | valid={len(X_valid)} | test={len(X_test)}")

                if len(X_valid) < MIN_VALID_SAMPLES or len(X_test) < MIN_TEST_SAMPLES:
                    logger.error(f"  ❌ valid/test خیلی کوچک (valid={len(X_valid)}, test={len(X_test)})")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'valid/test too small after 3-way split'}
                    results['summary']['failed'] += 1
                    continue

                if not HAS_LIGHTGBM:
                    logger.error("  LightGBM نصب نیست!")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'lightgbm not installed'}
                    results['summary']['failed'] += 1
                    continue

                n_neg = int((y_train == 0).sum())
                n_pos = int((y_train == 1).sum())
                scale = n_neg / max(n_pos, 1)

                model = lgb.LGBMClassifier(
                    n_estimators=300, max_depth=6, learning_rate=0.03, num_leaves=31,
                    min_child_samples=20, scale_pos_weight=scale, random_state=42,
                    n_jobs=-1, verbose=-1,
                )

                # ✅ FIX 5: patience از 30 به 75 افزایش یافت. با valid کوچک (~15%
                # داده)، لاگ‌لاس نویز زیادی دارد و patience=30 باعث می‌شد مدل
                # بعد از فقط ۱-۸ درخت (به‌جای واقعاً همگرا شدن) به‌اشتباه متوقف
                # شود — نه چون سیگنالی نبود، بلکه چون نویز validation کوچک آن
                # را پنهان می‌کرد.
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_valid, y_valid)],
                    callbacks=[lgb.early_stopping(75, verbose=False), lgb.log_evaluation(0)]
                )

                best_iter = getattr(model, 'best_iteration_', None) or model.n_estimators
                train_score = float(model.score(X_train, y_train))
                valid_score = float(model.score(X_valid, y_valid))
                test_score  = float(model.score(X_test, y_test))

                logger.info(f"  🌲 best_iteration_={best_iter}/300 | "
                            f"Train acc={train_score:.4f} | Valid acc={valid_score:.4f} | Test acc={test_score:.4f}")
                if best_iter < 20:
                    logger.warning(f"  ⚠️ {symbol}: مدل خیلی زود متوقف شد ({best_iter} درخت) — "
                                   f"احتمالاً سیگنال قابل‌یادگیری کم است")

                importances = dict(zip(FEAT_COLUMNS, model.feature_importances_))
                top = sorted(importances.items(), key=lambda x: -x[1])[:3]
                logger.info(f"  Top features: {[(k, int(v)) for k,v in top]}")

                proba_test = model.predict_proba(X_test)[:, 1] * 100.0
                y_test_arr = y_test.to_numpy()
                test_auc = _manual_auc(y_test_arr, proba_test / 100.0)
                test_logloss = _manual_log_loss(y_test_arr, proba_test / 100.0)
                auc_str = f"{test_auc:.3f}" if test_auc is not None else "N/A"
                logger.info(f"  📐 Test AUC={auc_str} | Test LogLoss={test_logloss:.4f}")

                if len(proba_test) >= MIN_TEST_SAMPLES_FOR_CALIBRATION:
                    suggested_threshold = float(np.percentile(proba_test, AI_THRESHOLD_PERCENTILE))
                    suggested_threshold = max(AI_THRESHOLD_MIN, min(AI_THRESHOLD_MAX, suggested_threshold))
                    calibration_note = f"per-symbol (n={len(proba_test)})"
                else:
                    suggested_threshold = float(getattr(config, 'AI_THRESHOLD', 65.0))
                    calibration_note = f"⚠️ fallback سراسری — n={len(proba_test)}"
                    logger.warning(f"  {calibration_note}")

                score_stats = {
                    'min':    round(float(np.min(proba_test)), 2) if len(proba_test) else None,
                    'p25':    round(float(np.percentile(proba_test, 25)), 2) if len(proba_test) else None,
                    'median': round(float(np.median(proba_test)), 2) if len(proba_test) else None,
                    'p75':    round(float(np.percentile(proba_test, 75)), 2) if len(proba_test) else None,
                    'max':    round(float(np.max(proba_test)), 2) if len(proba_test) else None,
                }
                logger.info(f"  📊 توزیع: min={score_stats['min']} p25={score_stats['p25']} "
                            f"median={score_stats['median']} p75={score_stats['p75']} max={score_stats['max']}")
                logger.info(f"  🎯 AI_THRESHOLD: {suggested_threshold:.2f} [{calibration_note}]")

                brain_sym = _brain_symbol(symbol)
                self.ai_thresholds[brain_sym] = {
                    'threshold': round(suggested_threshold, 2), 'percentile': AI_THRESHOLD_PERCENTILE,
                    'score_stats': score_stats, 'test_samples': len(proba_test),
                    'calibration': calibration_note,
                    'test_auc': round(test_auc, 4) if test_auc is not None else None,
                    'test_logloss': round(test_logloss, 4), 'best_iteration': int(best_iter),
                    'updated_at': datetime.now().isoformat(),
                }

                safe_name = _model_key(symbol)
                model_path = self.model_dir / f"{safe_name}_model.pkl"
                with open(model_path, 'wb') as f:
                    pickle.dump(model, f)
                logger.info(f"  ✅ ذخیره شد: {model_path}  (brain key: '{brain_sym}')")

                results['symbols'][symbol] = {
                    'status': 'SUCCESS', 'model_path': str(model_path), 'brain_key': brain_sym,
                    'train_score': train_score, 'valid_score': valid_score, 'test_score': test_score,
                    'test_auc': test_auc, 'test_logloss': test_logloss, 'best_iteration': int(best_iter),
                    'samples': len(X), 'tp_percent': round(tp_pct, 1), 'top_features': top,
                    'ai_threshold': round(suggested_threshold, 2), 'score_stats': score_stats,
                    'target_tp_ratio': sym_tp_ratio, 'target_sl_ratio': sym_sl_ratio,
                }
                results['summary']['successful'] += 1

            except Exception as e:
                logger.error(f"  خطا: {e}", exc_info=True)
                results['symbols'][symbol] = {'status': 'FAILED', 'reason': str(e)}
                results['summary']['failed'] += 1

        logger.info("\n" + "=" * 65)
        logger.info(f"نتیجه نهایی: {results['summary']['successful']} موفق, {results['summary']['failed']} ناموفق")

        aucs = [v.get('test_auc') for v in results['symbols'].values()
                if isinstance(v, dict) and v.get('status') == 'SUCCESS' and v.get('test_auc') is not None]
        if aucs:
            logger.info(f"📐 AUC میانگین همه‌ی نمادها: {np.mean(aucs):.3f} "
                        f"(min={min(aucs):.3f}, max={max(aucs):.3f})")

        return results

    def save_results(self, results, path: str = "training_results.json"):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"نتایج ذخیره شد: {path}")

    def save_ai_thresholds(self, path=None):
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
            logger.info(f"   {sym}: threshold={info['threshold']} | AUC={info.get('test_auc')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--monthly', action='store_true')
    args = parser.parse_args()

    logger.info("شروع pipeline آموزش LightGBM v13.0 (رفع ریشه‌ای leakage در early stopping)")
    logger.info(f"فیچرها: {FEAT_COLUMNS}")

    data_dir = os.path.join(BASE_DIR, "data", "4h")
    data_dict = {}

    for symbol in config.WATCHLIST:
        safe_name = symbol.replace("/", "_")
        filepath = os.path.join(data_dir, f"{safe_name}_history.csv")
        if not os.path.exists(filepath):
            logger.warning(f"فایل یافت نشد: {filepath}")
            continue
        try:
            df = pd.read_csv(filepath)
            col_map = {'Timestamp': 'timestamp', 'Open': 'open', 'High': 'high',
                       'Low': 'low', 'Close': 'close', 'Volume': 'volume'}
            df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)
            data_dict[symbol] = df
            logger.info(f"لود شد: {symbol} — {len(df)} ردیف")
        except Exception as e:
            logger.error(f"خطا در لود {symbol}: {e}")

    if not data_dict:
        logger.error("هیچ داده‌ای لود نشد!")
        sys.exit(1)

    logger.info(f"\n{len(data_dict)} ارز آماده: {list(data_dict.keys())}")

    model_dir = os.path.join(BASE_DIR, "src", "models")
    trainer = ModelTrainer(model_dir=model_dir)
    results = trainer.train_multiple_symbols(data_dict)

    trainer.save_results(results, os.path.join(BASE_DIR, "training_results.json"))
    trainer.save_ai_thresholds()

    if results['summary']['successful'] == 0:
        logger.error("هیچ مدلی ذخیره نشد!")
        sys.exit(1)

    logger.info("✅ Pipeline با موفقیت تمام شد.")
    sys.exit(0)

"""
FILE PATH: src/train_model.py (v14.0 - Pooled multi-symbol training)
تغییرات نسبت به v13.1:

  🔴 یافته‌ی قطعی از لاگ‌های واقعی: با آموزش جدا برای هر ارز، فقط BTCUSDT
     برتری ضعیف ولی واقعی نشان داد (AUC=0.557)؛ ۹ ارز دیگر AUC≈0.45-0.50
     داشتند (عملاً تصادفی) و مدل با ۱-۲ درخت متوقف می‌شد. افزایش patience
     کمکی نکرد چون مشکل patience نبود — با فقط ~۱۵۰۰-۲۰۰۰ نمونه‌ی train
     per-symbol، برای اکثر ارزها داده به‌سادگی برای تشخیص یک الگوی ضعیف
     از نویز کافی نیست.

  ✅ FIX ریشه‌ای: به‌جای ۱۱ مدل جدا، یک مدل LightGBM مشترک (pooled) روی
     داده‌ی ترکیبی همه‌ی ارزها آموزش داده می‌شود (~۱۰ برابر حجم نمونه‌ی
     train هر مدل تکی). split زمانی (train/valid/test) ابتدا per-symbol
     انجام می‌شود (برای جلوگیری از نشت زمانی)، سپس بخش‌های مشابه از همه‌ی
     ارزها به هم می‌پیوندند.
  ✅ کالیبراسیون AI_THRESHOLD همچنان per-symbol باقی می‌ماند — هر ارز روی
     برش خودش از test مشترک، صدک جداگانه می‌گیرد.
  ✅ مدل مشترک زیر نام فایل هر ارز جداگانه ذخیره می‌شود (مثلاً
     BTC_USDT_model.pkl, ETH_USDT_model.pkl, ...) — یعنی brain.py،
     strategy.py، backtester.py، optimizer.py هیچ تغییری نیاز ندارند،
     چون همچنان انتظار «یک فایل مدل به ازای هر ارز» را دارند و همین برآورده
     می‌شود؛ فقط محتوای همه‌ی فایل‌ها یکی است.
  ✅ گزارش AUC/logloss هم overall (روی کل test مشترک) و هم per-symbol
     (روی برش هر ارز از همان test) لاگ می‌شود تا مشخص شود آیا مدل مشترک
     برای همه‌ی ارزها به یک اندازه مفید است یا نه.
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
from typing import Dict, Optional, Tuple, List
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
# باقی‌مانده (~۰.۱۵) هر ارز = سهم آن ارز در test مشترک

# حداقل نمونه‌ی هر ارز (قبل از تقسیم) تا در pooled training شرکت کند
MIN_SYMBOL_SAMPLES = 150
MIN_VALID_SAMPLES  = 30
MIN_TEST_SAMPLES   = 30
MIN_TEST_SAMPLES_FOR_CALIBRATION = 30

AI_THRESHOLD_PERCENTILE = float(getattr(config, 'AI_THRESHOLD_PERCENTILE', 60))
AI_THRESHOLD_MIN = float(getattr(config, 'AI_THRESHOLD_MIN', 20.0))
AI_THRESHOLD_MAX = float(getattr(config, 'AI_THRESHOLD_MAX', 80.0))

AI_THRESHOLDS_FILE = os.path.join(BASE_DIR, 'ai_thresholds.json')


# ─── معیارهای تشخیصی دستی (بدون وابستگی به scikit-learn) ────────────────────

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


# ─── تابع target — یکسان با v13.1 (آستانه‌ی RSI=50، هماهنگ با strategy.py) ──

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
        for j in range(i + 1, min(i + TARGET_LOOKAHEAD + 1, n)):
            h = float(high[j]); l = float(low[j])
            if direction == 'LONG':
                if l <= sl_price: break
                if h >= tp_price: hit_tp = True; break
            else:
                if h >= sl_price: break
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


# ─── ModelTrainer (Pooled) ────────────────────────────────────────────────────

class ModelTrainer:

    def __init__(self, model_dir: str = "./models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.ai_thresholds: Dict[str, Dict] = {}

    def _prepare_symbol(self, symbol: str, df: pd.DataFrame, best_params: Dict) -> Optional[dict]:
        """اندیکاتورها + target + warm-up + فیلتر حجم + تقسیم زمانی سه‌بخشی
        برای یک ارز. None برمی‌گرداند اگر داده کافی نباشد."""
        if HAS_INDICATORS:
            df_feat, meta = TechnicalIndicators.calculate_all_features(df, symbol=symbol, min_rows_required=100)
            if not meta.get('success', False):
                logger.error(f"  اندیکاتورها ناموفق برای {symbol}: {meta.get('missing_features')}")
                return None
        else:
            df_feat = df.copy()

        sym_tp_ratio, sym_sl_ratio = _get_symbol_tp_sl(symbol, best_params)
        df_feat['target'] = _build_target(df_feat, symbol, tp_ratio=sym_tp_ratio, sl_ratio=sym_sl_ratio)

        if len(df_feat) > WARMUP_ROWS:
            df_feat = df_feat.iloc[WARMUP_ROWS:].reset_index(drop=True)
        else:
            logger.warning(f"  ⚠️ {symbol}: طول داده ({len(df_feat)}) کمتر از warm-up ({WARMUP_ROWS}) — رد شد")

        df_feat = _apply_volume_filter(df_feat, symbol)

        missing = [f for f in FEAT_COLUMNS if f not in df_feat.columns]
        if missing:
            logger.error(f"  فیچرهای گمشده برای {symbol}: {missing}")
            return None

        X = df_feat[FEAT_COLUMNS].copy()
        y = df_feat['target'].copy()
        valid_mask = X.notna().all(axis=1) & y.notna()
        X, y = X[valid_mask].reset_index(drop=True), y[valid_mask].reset_index(drop=True)

        if len(X) < MIN_SYMBOL_SAMPLES:
            logger.warning(f"  ⚠️ {symbol}: نمونه ناکافی ({len(X)} < {MIN_SYMBOL_SAMPLES}) — از pooled training کنار گذاشته شد")
            return None

        n = len(X)
        split_train = int(n * TRAIN_FRAC)
        split_valid = int(n * (TRAIN_FRAC + VALID_FRAC))
        X_tr, y_tr = X.iloc[:split_train], y.iloc[:split_train]
        X_va, y_va = X.iloc[split_train:split_valid], y.iloc[split_train:split_valid]
        X_te, y_te = X.iloc[split_valid:], y.iloc[split_valid:]

        if len(X_va) < MIN_VALID_SAMPLES or len(X_te) < MIN_TEST_SAMPLES:
            logger.warning(f"  ⚠️ {symbol}: valid/test خیلی کوچک بعد از split (valid={len(X_va)}, test={len(X_te)}) — کنار گذاشته شد")
            return None

        tp_pct = float((y == 1).mean() * 100)
        logger.info(f"  {symbol}: {len(X)} نمونه (TP={tp_pct:.1f}%) | "
                    f"train={len(X_tr)} valid={len(X_va)} test={len(X_te)}")

        return {
            'X_tr': X_tr, 'y_tr': y_tr, 'X_va': X_va, 'y_va': y_va, 'X_te': X_te, 'y_te': y_te,
            'tp_ratio': sym_tp_ratio, 'sl_ratio': sym_sl_ratio, 'tp_pct': tp_pct, 'samples': len(X),
        }

    def train_multiple_symbols(self, data_dict: Dict[str, pd.DataFrame]) -> Dict:
        results = {
            'timestamp':  datetime.now().isoformat(),
            'model_type': 'LightGBM (pooled, shared across symbols)',
            'features':   FEAT_COLUMNS,
            'target':     f'SL/TP simulation (lookahead={TARGET_LOOKAHEAD} candles)',
            'ai_threshold_percentile': AI_THRESHOLD_PERCENTILE,
            'symbols':    {},
            'pooled':     {},
            'summary':    {'total': len(data_dict), 'successful': 0, 'failed': 0}
        }

        logger.info(f"شروع pooled-training برای {len(data_dict)} symbol")
        logger.info(f"فیچرها ({len(FEAT_COLUMNS)}): {FEAT_COLUMNS}")
        logger.info(f"تقسیم زمانی per-symbol: train={TRAIN_FRAC:.0%} / valid={VALID_FRAC:.0%} / "
                    f"test={1-TRAIN_FRAC-VALID_FRAC:.0%} — سپس همه‌ی ارزها با هم ترکیب می‌شوند")
        logger.info(f"warm-up: {WARMUP_ROWS} ردیف اول هر ارز حذف می‌شود")
        logger.info("=" * 65)

        best_params = _load_best_params()
        if best_params:
            logger.info(f"✅ best_params.json یافت شد — {len([k for k in best_params if not k.startswith('_')])} ارز کالیبره‌شده")

        # ── مرحله ۱: آماده‌سازی per-symbol ──────────────────────────────────
        prepared: Dict[str, dict] = {}
        for symbol, df in data_dict.items():
            logger.info(f"\nآماده‌سازی: {symbol}")
            info = self._prepare_symbol(symbol, df, best_params)
            if info is None:
                results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'insufficient data for pooled training'}
                results['summary']['failed'] += 1
            else:
                prepared[symbol] = info

        if not prepared:
            logger.error("❌ هیچ نمادی داده‌ی کافی برای pooled training نداشت — training متوقف شد")
            return results

        if not HAS_LIGHTGBM:
            logger.error("LightGBM نصب نیست!")
            for symbol in prepared:
                results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'lightgbm not installed'}
                results['summary']['failed'] += 1
            return results

        # ── مرحله ۲: ترکیب (pool) کردن train/valid/test همه‌ی ارزها ─────────
        X_train_all = pd.concat([d['X_tr'] for d in prepared.values()], ignore_index=True)
        y_train_all = pd.concat([d['y_tr'] for d in prepared.values()], ignore_index=True)
        X_valid_all = pd.concat([d['X_va'] for d in prepared.values()], ignore_index=True)
        y_valid_all = pd.concat([d['y_va'] for d in prepared.values()], ignore_index=True)

        test_frames, test_targets, test_symbol_tags = [], [], []
        for sym, d in prepared.items():
            test_frames.append(d['X_te'])
            test_targets.append(d['y_te'])
            test_symbol_tags.extend([sym] * len(d['X_te']))
        X_test_all = pd.concat(test_frames, ignore_index=True)
        y_test_all = pd.concat(test_targets, ignore_index=True)
        test_symbol_tags = np.array(test_symbol_tags)

        logger.info(
            f"\n📦 Pooled dataset: train={len(X_train_all)} | valid={len(X_valid_all)} | "
            f"test={len(X_test_all)} (از {len(prepared)} نماد)"
        )

        # ── مرحله ۳: آموزش یک مدل مشترک ──────────────────────────────────────
        n_neg = int((y_train_all == 0).sum())
        n_pos = int((y_train_all == 1).sum())
        scale = n_neg / max(n_pos, 1)

        model = lgb.LGBMClassifier(
            n_estimators=500, max_depth=6, learning_rate=0.03, num_leaves=31,
            min_child_samples=50, scale_pos_weight=scale, random_state=42,
            n_jobs=-1, verbose=-1,
        )
        model.fit(
            X_train_all, y_train_all,
            eval_set=[(X_valid_all, y_valid_all)],
            callbacks=[lgb.early_stopping(75, verbose=False), lgb.log_evaluation(0)]
        )

        best_iter = getattr(model, 'best_iteration_', None) or model.n_estimators
        train_score = float(model.score(X_train_all, y_train_all))
        valid_score = float(model.score(X_valid_all, y_valid_all))
        test_score  = float(model.score(X_test_all, y_test_all))

        proba_test_all = model.predict_proba(X_test_all)[:, 1] * 100.0
        y_test_arr_all = y_test_all.to_numpy()
        overall_auc     = _manual_auc(y_test_arr_all, proba_test_all / 100.0)
        overall_logloss = _manual_log_loss(y_test_arr_all, proba_test_all / 100.0)

        importances = dict(zip(FEAT_COLUMNS, model.feature_importances_))
        top = sorted(importances.items(), key=lambda x: -x[1])[:5]

        auc_str = f"{overall_auc:.3f}" if overall_auc is not None else "N/A"
        logger.info(
            f"\n🌲 Pooled best_iteration_={best_iter}/500 | "
            f"Train acc={train_score:.4f} | Valid acc={valid_score:.4f} | Test acc={test_score:.4f}"
        )
        logger.info(f"📐 Overall Test AUC={auc_str} | Overall Test LogLoss={overall_logloss:.4f}")
        logger.info(f"🔝 Top features (pooled): {[(k, int(v)) for k, v in top]}")
        if best_iter < 20:
            logger.warning(
                f"⚠️ حتی با pooled training مدل زود متوقف شد ({best_iter} درخت) — "
                f"احتمالاً این ۸ فیچر برای این برچسب سقف پیش‌بینی‌پذیری‌شان نزدیک "
                f"است، صرف‌نظر از حجم داده. قدم بعدی باید فیچرهای غنی‌تر یا "
                f"بازتعریف برچسب باشد، نه صرفاً بیشتر کردن داده."
            )

        results['pooled'] = {
            'train_size': len(X_train_all), 'valid_size': len(X_valid_all), 'test_size': len(X_test_all),
            'best_iteration': int(best_iter), 'train_score': train_score, 'valid_score': valid_score,
            'test_score': test_score, 'overall_test_auc': overall_auc, 'overall_test_logloss': overall_logloss,
            'top_features': top, 'symbols_included': list(prepared.keys()),
        }

        # ── مرحله ۴: per-symbol — AUC breakdown + کالیبراسیون + ذخیره‌ی مدل ──
        for symbol, d in prepared.items():
            mask = (test_symbol_tags == symbol)
            proba_sym = proba_test_all[mask]
            y_sym     = y_test_arr_all[mask]

            sym_auc     = _manual_auc(y_sym, proba_sym / 100.0)
            sym_logloss = _manual_log_loss(y_sym, proba_sym / 100.0) if len(proba_sym) else None
            sym_auc_str = f"{sym_auc:.3f}" if sym_auc is not None else "N/A"

            if len(proba_sym) >= MIN_TEST_SAMPLES_FOR_CALIBRATION:
                suggested_threshold = float(np.percentile(proba_sym, AI_THRESHOLD_PERCENTILE))
                suggested_threshold = max(AI_THRESHOLD_MIN, min(AI_THRESHOLD_MAX, suggested_threshold))
                calibration_note = f"per-symbol از pooled model (n={len(proba_sym)})"
            else:
                suggested_threshold = float(getattr(config, 'AI_THRESHOLD', 65.0))
                calibration_note = f"⚠️ fallback سراسری — n={len(proba_sym)}"

            score_stats = {
                'min':    round(float(np.min(proba_sym)), 2) if len(proba_sym) else None,
                'p25':    round(float(np.percentile(proba_sym, 25)), 2) if len(proba_sym) else None,
                'median': round(float(np.median(proba_sym)), 2) if len(proba_sym) else None,
                'p75':    round(float(np.percentile(proba_sym, 75)), 2) if len(proba_sym) else None,
                'max':    round(float(np.max(proba_sym)), 2) if len(proba_sym) else None,
            }

            logger.info(
                f"  {symbol}: test_n={len(proba_sym)} | AUC={sym_auc_str} | "
                f"threshold={suggested_threshold:.2f} | dist(min/median/max)="
                f"{score_stats['min']}/{score_stats['median']}/{score_stats['max']}"
            )

            brain_sym = _brain_symbol(symbol)
            self.ai_thresholds[brain_sym] = {
                'threshold': round(suggested_threshold, 2), 'percentile': AI_THRESHOLD_PERCENTILE,
                'score_stats': score_stats, 'test_samples': len(proba_sym),
                'calibration': calibration_note,
                'test_auc': round(sym_auc, 4) if sym_auc is not None else None,
                'test_logloss': round(sym_logloss, 4) if sym_logloss is not None else None,
                'model_type': 'pooled', 'pooled_best_iteration': int(best_iter),
                'updated_at': datetime.now().isoformat(),
            }

            # ✅ مدل مشترک زیر نام فایل هر ارز ذخیره می‌شود — brain.py/strategy.py
            # بدون تغییر کار می‌کنند چون همچنان یک فایل per-symbol پیدا می‌کنند.
            safe_name  = _model_key(symbol)
            model_path = self.model_dir / f"{safe_name}_model.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)

            results['symbols'][symbol] = {
                'status': 'SUCCESS', 'model_path': str(model_path), 'brain_key': brain_sym,
                'model_type': 'pooled', 'pooled_best_iteration': int(best_iter),
                'test_auc': sym_auc, 'test_logloss': sym_logloss,
                'samples': d['samples'], 'tp_percent': round(d['tp_pct'], 1),
                'ai_threshold': round(suggested_threshold, 2), 'score_stats': score_stats,
                'target_tp_ratio': d['tp_ratio'], 'target_sl_ratio': d['sl_ratio'],
            }
            results['summary']['successful'] += 1

        logger.info("\n" + "=" * 65)
        logger.info(f"نتیجه نهایی: {results['summary']['successful']} موفق, {results['summary']['failed']} ناموفق")
        logger.info(f"📐 Overall Pooled AUC: {auc_str} — این عدد کلی‌ترین معیار سلامت مدل است")

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

    logger.info("شروع pipeline آموزش LightGBM v14.0 (pooled multi-symbol training)")
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

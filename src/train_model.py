"""
FILE PATH: src/train_model.py (v11.0 - Aligned with live pipeline)
تغییرات نسبت به v10.0:
  ✅ target واقعی: شبیه‌سازی SL/TP روی داده تاریخی (نه کندل بعدی)
  ✅ feat_volume_ratio به FEAT_COLUMNS اضافه شد (8 فیچر)
  ✅ فیلتر حجم قبل از training اعمال می‌شود (یکسان با لایو)
  ✅ نام مدل با BTC/USDT ذخیره می‌شود (سازگار با brain.py)
  ✅ shuffle=False برای داده‌های زمانی (بدون data leakage)
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

# ─── فیچرها: ۸ فیچر (+ feat_volume_ratio نسبت به v10) ───────────────────────
FEAT_COLUMNS = [
    'feat_adx',
    'feat_atr_percent',
    'feat_rsi',
    'feat_trend_line',
    'feat_ema_deviation',
    'feat_rsi_momentum',
    'feat_body_ratio',
    'feat_volume_ratio',   # ✅ اضافه شد
]

MIN_TRAINING_SAMPLES = 50

# ─── پارامترهای target ───────────────────────────────────────────────────────
# چند کندل به جلو برای بررسی رسیدن به SL یا TP
TARGET_LOOKAHEAD = 20   # 20 کندل ۴ ساعته = ۸۰ ساعت


# ─── تابع اصلی target ────────────────────────────────────────────────────────

def _build_target(df: pd.DataFrame, symbol: str) -> pd.Series:
    """
    شبیه‌سازی واقعی SL/TP روی داده تاریخی.

    برای هر کندل که شرط شکست (breakout) برقرار است:
      - SL  = entry - 1.5 * ATR * SL_RATIO
      - TP2 = entry + 1.5 * ATR * TP_RATIO   (برای LONG)

    اگر در TARGET_LOOKAHEAD کندل بعدی:
      - قیمت به TP2 رسید → label = 1  (موفق)
      - قیمت به SL رسید  → label = 0  (ناموفق)
      - هیچ‌کدام        → label = 0  (timeout — محافظه‌کارانه)

    فقط کندل‌هایی که شرط breakout دارند label می‌گیرند؛
    بقیه NaN هستند و در training استفاده نمی‌شوند.
    """
    sl_ratio = float(getattr(config, 'SL_RATIO',  1.0))
    tp_ratio = float(getattr(config, 'TP_RATIO',  2.0))
    max_sl   = float(getattr(config, 'MAX_SL_PERCENT', 0.05))

    # ستون‌های مورد نیاز
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

        # تعیین جهت بر اساس RSI (ساده‌سازی — swing در runtime تعریف می‌شود)
        # اگر RSI > 50 → LONG، RSI < 50 → SHORT
        cur_rsi = float(rsi[i])

        if cur_rsi > 52:           # LONG
            sl_price  = entry - sl_dist
            tp_price  = entry + sl_dist * tp_ratio
            direction = 'LONG'
        elif cur_rsi < 48:         # SHORT
            sl_price  = entry + sl_dist
            tp_price  = entry - sl_dist * tp_ratio
            direction = 'SHORT'
        else:
            continue               # ناحیه خنثی — label نمی‌دهیم

        # بررسی کندل‌های بعدی
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
            else:  # SHORT
                if h >= sl_price:
                    hit_sl = True; break
                if l <= tp_price:
                    hit_tp = True; break

        target[i] = 1 if hit_tp else 0

    result = pd.Series(target, index=df.index, name='target')
    tp_count = int((result == 1).sum())
    sl_count = int((result == 0).sum())
    logger.info(
        f"  target: TP={tp_count} ({tp_count/(tp_count+sl_count)*100:.1f}%) "
        f"SL/timeout={sl_count} ({sl_count/(tp_count+sl_count)*100:.1f}%) "
        f"(از {n} کندل)"
    )
    return result


# ─── فیلتر حجم (یکسان با strategy.py و backtester.py) ───────────────────────

# فیلتر حجم از ماژول مشترک src/volume_filter.py


def _apply_volume_filter(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    فیلتر حجم پویا — یکسان با strategy.py و backtester.py.
    volume >= Volume_SMA_20 * VOLUME_MULTIPLIER (0.5)
    """
    if apply_volume_filter_df is not None:
        return apply_volume_filter_df(df, symbol)
    return df


# ─── نام امن مدل (سازگار با brain.py) ───────────────────────────────────────

def _model_key(symbol: str) -> str:
    """
    کلیدی که brain.py برای جستجو استفاده می‌کند.

    brain.py:
        symbol = filename.stem.replace('_model', '').replace('_', '/')
    پس اگر WATCHLIST=['BTCUSDT']:
        safe_name = 'BTCUSDT'
        filename  = 'BTCUSDT_model.pkl'
        brain key = 'BTCUSDT_model'.replace('_model','')='BTCUSDT'
                    .replace('_','/')='BTCUSDT'  ← بدون اسلش
    اما _to_brain_symbol('BTCUSDT') = 'BTC/USDT'
    → brain با 'BTC/USDT' جستجو می‌کند اما مدل با 'BTCUSDT' ذخیره شده → پیدا نمی‌شود!

    راه‌حل: مدل را با کلید 'BTC_USDT' ذخیره کنیم تا brain.py
             آن را با 'BTC/USDT' پیدا کند:
             'BTC_USDT_model.pkl' → stem='BTC_USDT_model'
             → replace('_model','')='BTC_USDT'
             → replace('_','/')='BTC/USDT' ✅
    """
    # BTCUSDT → BTC/USDT → BTC_USDT
    if '/' not in symbol and 'USDT' in symbol:
        base   = symbol.replace('USDT', '')
        symbol = f"{base}/USDT"
    return symbol.replace('/', '_')


# ─── ModelTrainer ─────────────────────────────────────────────────────────────

class ModelTrainer:

    def __init__(self, model_dir: str = "./models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def train_multiple_symbols(
        self,
        data_dict: Dict[str, pd.DataFrame],
    ) -> Dict:

        results = {
            'timestamp':  datetime.now().isoformat(),
            'model_type': 'LightGBM',
            'features':   FEAT_COLUMNS,
            'target':     f'SL/TP simulation (lookahead={TARGET_LOOKAHEAD} candles)',
            'symbols':    {},
            'summary':    {'total': len(data_dict), 'successful': 0, 'failed': 0}
        }

        logger.info(f"شروع training برای {len(data_dict)} symbol")
        logger.info(f"فیچرها ({len(FEAT_COLUMNS)}): {FEAT_COLUMNS}")
        logger.info("=" * 65)

        for symbol, df in data_dict.items():
            logger.info(f"\nپردازش: {symbol}")

            # ── ۱. محاسبه اندیکاتورها ────────────────────────────────────────
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

            # ── ۲. فیلتر حجم (یکسان با لایو) ────────────────────────────────
            df_feat = _apply_volume_filter(df_feat, symbol)

            # ── ۳. ساختن target واقعی (SL/TP simulation) ────────────────────
            df_feat['target'] = _build_target(df_feat, symbol)

            # ── ۴. بررسی فیچرها ──────────────────────────────────────────────
            missing = [f for f in FEAT_COLUMNS if f not in df_feat.columns]
            if missing:
                logger.error(f"  فیچرهای گمشده: {missing}")
                results['symbols'][symbol] = {'status': 'FAILED', 'reason': f'missing: {missing}'}
                results['summary']['failed'] += 1
                continue

            # ── ۵. آماده‌سازی X, y ───────────────────────────────────────────
            try:
                X = df_feat[FEAT_COLUMNS].copy()
                y = df_feat['target'].copy()

                # حذف ردیف‌های NaN (کندل‌های بدون label)
                valid = X.notna().all(axis=1) & y.notna()
                X, y  = X[valid], y[valid]

                if len(X) < MIN_TRAINING_SAMPLES:
                    logger.error(f"  نمونه ناکافی: {len(X)} < {MIN_TRAINING_SAMPLES}")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'insufficient samples'}
                    results['summary']['failed'] += 1
                    continue

                # توزیع کلاس‌ها
                tp_pct = float((y == 1).mean() * 100)
                logger.info(f"  {len(X)} نمونه | TP={tp_pct:.1f}% | SL={100-tp_pct:.1f}%")

                # ── ۶. تقسیم زمانی (بدون shuffle) ───────────────────────────
                # ✅ FIX: shuffle=False — داده زمانی باید ترتیب حفظ شود
                split  = int(len(X) * 0.8)
                X_train, X_test = X.iloc[:split], X.iloc[split:]
                y_train, y_test = y.iloc[:split], y.iloc[split:]

                logger.info(f"  train={len(X_train)} | test={len(X_test)}")

                if not HAS_LIGHTGBM:
                    logger.error("  LightGBM نصب نیست!")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'lightgbm not installed'}
                    results['summary']['failed'] += 1
                    continue

                # ── ۷. آموزش مدل ─────────────────────────────────────────────
                # scale_pos_weight برای جبران عدم تعادل کلاس‌ها
                n_neg = int((y_train == 0).sum())
                n_pos = int((y_train == 1).sum())
                scale = n_neg / max(n_pos, 1)

                model = lgb.LGBMClassifier(
                    n_estimators=300,
                    max_depth=6,
                    learning_rate=0.03,
                    num_leaves=31,
                    min_child_samples=20,
                    scale_pos_weight=scale,   # جبران عدم تعادل TP/SL
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

                # feature importance
                importances = dict(zip(FEAT_COLUMNS, model.feature_importances_))
                top = sorted(importances.items(), key=lambda x: -x[1])[:3]
                logger.info(f"  Top features: {[(k, int(v)) for k,v in top]}")

                # ── ۸. ذخیره مدل با نام سازگار با brain.py ──────────────────
                # ✅ FIX: BTC_USDT_model.pkl → brain.py آن را با کلید 'BTC/USDT' پیدا می‌کند
                safe_name  = _model_key(symbol)
                model_path = self.model_dir / f"{safe_name}_model.pkl"

                with open(model_path, 'wb') as f:
                    pickle.dump(model, f)

                logger.info(f"  ✅ ذخیره شد: {model_path}  (brain key: '{symbol}')")

                results['symbols'][symbol] = {
                    'status':      'SUCCESS',
                    'model_path':  str(model_path),
                    'brain_key':   symbol,
                    'train_score': train_score,
                    'test_score':  test_score,
                    'samples':     len(X),
                    'tp_percent':  round(tp_pct, 1),
                    'top_features': top,
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


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--monthly', action='store_true')
    args = parser.parse_args()

    logger.info("شروع pipeline آموزش LightGBM v11.0")
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

            # نرمال‌سازی نام ستون‌ها
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

    if results['summary']['successful'] == 0:
        logger.error("هیچ مدلی ذخیره نشد!")
        sys.exit(1)

    logger.info("✅ Pipeline با موفقیت تمام شد.")
    sys.exit(0)

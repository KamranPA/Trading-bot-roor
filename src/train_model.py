"""
FILE PATH: src/train_model.py (v10.0 - LightGBM + feat_* features)
همه فیچرها با feat_* و مدل LightGBM - سازگار با brain.py و optimizer.py
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
from typing import Dict, Optional
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config

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

from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# این همان ۷ فیچری است که brain.py و optimizer.py استفاده می‌کنند
FEAT_COLUMNS = [
    'feat_adx',
    'feat_atr_percent',
    'feat_rsi',
    'feat_trend_line',
    'feat_ema_deviation',
    'feat_rsi_momentum',
    'feat_body_ratio',
]

MIN_TRAINING_SAMPLES = 50


class ModelTrainer:

    def __init__(self, model_dir: str = "./models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, symbol: str) -> str:
        return symbol.replace("/", "_").replace("\\", "_")

    def train_multiple_symbols(
        self,
        data_dict: Dict[str, pd.DataFrame],
        target_column: str = 'target'
    ) -> Dict:

        results = {
            'timestamp': datetime.now().isoformat(),
            'model_type': 'LightGBM',
            'features': FEAT_COLUMNS,
            'symbols': {},
            'summary': {'total': len(data_dict), 'successful': 0, 'failed': 0}
        }

        logger.info(f"شروع training برای {len(data_dict)} symbol با LightGBM")
        logger.info("=" * 60)

        for symbol, df in data_dict.items():
            logger.info(f"\nپردازش: {symbol}")

            # محاسبه اندیکاتورها
            if HAS_INDICATORS:
                df_feat, meta = TechnicalIndicators.calculate_all_features(
                    df, symbol=symbol, min_rows_required=100
                )
                if not meta.get('success', False):
                    logger.error(f"  محاسبه اندیکاتورها ناموفق: {meta.get('missing_features')}")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'indicators failed'}
                    results['summary']['failed'] += 1
                    continue
            else:
                df_feat = df.copy()

            # بررسی وجود فیچرهای feat_*
            missing = [f for f in FEAT_COLUMNS if f not in df_feat.columns]
            if missing:
                logger.error(f"  فیچرهای گمشده: {missing}")
                results['symbols'][symbol] = {'status': 'FAILED', 'reason': f'missing features: {missing}'}
                results['summary']['failed'] += 1
                continue

            # بررسی target
            if target_column not in df_feat.columns:
                logger.error(f"  ستون '{target_column}' یافت نشد")
                results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'no target column'}
                results['summary']['failed'] += 1
                continue

            try:
                X = df_feat[FEAT_COLUMNS].copy()
                y = df_feat[target_column].copy()

                valid = X.notna().all(axis=1) & y.notna()
                X, y = X[valid], y[valid]

                if len(X) < MIN_TRAINING_SAMPLES:
                    logger.error(f"  نمونه ناکافی: {len(X)} < {MIN_TRAINING_SAMPLES}")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'insufficient samples'}
                    results['summary']['failed'] += 1
                    continue

                logger.info(f"  {len(X)} نمونه - فیچرها: {FEAT_COLUMNS}")

                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=0.2, random_state=42
                )

                if not HAS_LIGHTGBM:
                    logger.error("  LightGBM نصب نیست!")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'lightgbm not installed'}
                    results['summary']['failed'] += 1
                    continue

                model = lgb.LGBMClassifier(
                    n_estimators=200,
                    max_depth=8,
                    learning_rate=0.05,
                    num_leaves=31,
                    min_child_samples=20,
                    random_state=42,
                    n_jobs=-1,
                    verbose=-1
                )

                model.fit(
                    X_train, y_train,
                    eval_set=[(X_test, y_test)],
                    callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(0)]
                )

                train_score = model.score(X_train, y_train)
                test_score  = model.score(X_test,  y_test)
                logger.info(f"  Train: {train_score:.4f} | Test: {test_score:.4f}")

                # ذخیره با نام امن: BTC_USDT_model.pkl
                safe_name  = self._safe_name(symbol)
                model_path = self.model_dir / f"{safe_name}_model.pkl"

                with open(model_path, 'wb') as f:
                    pickle.dump(model, f)

                logger.info(f"  ذخیره شد: {model_path}")

                results['symbols'][symbol] = {
                    'status': 'SUCCESS',
                    'model_path': str(model_path),
                    'train_score': float(train_score),
                    'test_score':  float(test_score),
                    'samples': len(X),
                }
                results['summary']['successful'] += 1

            except Exception as e:
                logger.error(f"  خطا: {e}", exc_info=True)
                results['symbols'][symbol] = {'status': 'FAILED', 'reason': str(e)}
                results['summary']['failed'] += 1

        logger.info("\n" + "=" * 60)
        logger.info(f"نتیجه: {results['summary']['successful']} موفق, {results['summary']['failed']} ناموفق")
        return results

    def save_results(self, results: Dict, path: str = "training_results.json"):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"نتایج ذخیره شد: {path}")


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--monthly', action='store_true')
    args = parser.parse_args()

    logger.info("شروع pipeline آموزش LightGBM")

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

            # نرمال‌سازی نام ستون‌ها — indicators.py به lowercase نیاز دارد
            col_map = {
                'Timestamp': 'timestamp', 'Open': 'open',
                'High': 'high', 'Low': 'low',
                'Close': 'close', 'Volume': 'volume',
            }
            df.rename(columns=col_map, inplace=True)

            # ساختن target: کندل بعدی صعودی = 1
            df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
            df.dropna(subset=['target'], inplace=True)

            data_dict[symbol] = df
            logger.info(f"لود شد: {symbol} - {len(df)} ردیف")

        except Exception as e:
            logger.error(f"خطا در لود {symbol}: {e}")

    if not data_dict:
        logger.error("هیچ داده‌ای لود نشد!")
        logger.error(f"مسیر: {data_dir}")
        sys.exit(1)

    logger.info(f"{len(data_dict)} ارز آماده: {list(data_dict.keys())}")

    model_dir = os.path.join(BASE_DIR, "src", "models")
    trainer   = ModelTrainer(model_dir=model_dir)
    results   = trainer.train_multiple_symbols(data_dict, target_column='target')

    trainer.save_results(results, os.path.join(BASE_DIR, "training_results.json"))

    if results['summary']['successful'] == 0:
        logger.error("هیچ مدلی ذخیره نشد!")
        sys.exit(1)

    logger.info("Pipeline با موفقیت تمام شد.")
    sys.exit(0)

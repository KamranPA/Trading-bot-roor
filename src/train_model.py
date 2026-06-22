"""
FILE PATH: src/train_model.py
بهبود شده: main block کامل + نام‌گذاری درست pkl + پشتیبانی از --monthly
"""

import pandas as pd
import numpy as np
import pickle
import logging
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Optional
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import json
from datetime import datetime

# تنظیم مسیر برای import
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from indicators import TechnicalIndicators
import config

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class ModelTrainer:
    """کلاس برای training Random Forest models"""

    DEFAULT_CONFIG = {
        'test_size': 0.2,
        'random_state': 42,
        'n_estimators': 100,
        'max_depth': 15,
        'min_samples_split': 5,
        'min_samples_leaf': 2,
    }

    MIN_TRAINING_SAMPLES = 50

    REQUIRED_FEATURES = [
        'ATR', 'EMA_diff', 'RSI', 'MACD', 'ADX',
        'BB_upper', 'BB_lower', 'OBV', 'Volume_SMA'
    ]

    def __init__(self, model_dir: str = "./models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.models = {}
        self.scalers = {}

    def _safe_symbol_name(self, symbol: str) -> str:
        """تبدیل BTC/USDT به BTC_USDT برای نام فایل"""
        return symbol.replace("/", "_").replace(" ", "_")

    def train_multiple_symbols(
        self,
        data_dict: Dict[str, pd.DataFrame],
        volume_threshold: Optional[Dict[str, float]] = None,
        target_column: str = 'target'
    ) -> Dict:

        results = {
            'timestamp': datetime.now().isoformat(),
            'symbols': {},
            'summary': {
                'total_symbols': len(data_dict),
                'successful': 0,
                'failed': 0,
            }
        }

        logger.info(f"🚀 شروع training برای {len(data_dict)} symbol")
        logger.info("=" * 70)

        for symbol, df in data_dict.items():
            logger.info(f"\n📊 پردازش: {symbol}")
            logger.info("-" * 70)

            # STEP 1: محاسبه اندیکاتورها
            logger.info("  1️⃣ محاسبه اندیکاتورهای تکنیکال...")
            df_with_features, feature_meta = TechnicalIndicators.calculate_all_features(
                df,
                symbol=symbol,
                min_rows_required=100
            )

            if not feature_meta['success']:
                logger.error(f"  ❌ محاسبه ویژگی‌ها ناموفق: {feature_meta.get('missing_features', '')}")
                results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'Feature calculation failed'}
                results['summary']['failed'] += 1
                continue

            logger.info(f"  ✅ {feature_meta['valid_rows']} ردیف معتبر")

            # STEP 2: فیلتر حجم (اختیاری)
            if volume_threshold and symbol in volume_threshold:
                vol_thresh = volume_threshold[symbol]
                rows_before = len(df_with_features)
                df_with_features = df_with_features[
                    df_with_features['volume'] >= vol_thresh
                ].copy()
                rows_after = len(df_with_features)
                logger.info(f"  2️⃣ فیلتر حجم: {rows_after}/{rows_before} باقی ماند")

                if rows_after < self.MIN_TRAINING_SAMPLES:
                    logger.error(f"  ❌ داده ناکافی بعد از فیلتر ({rows_after} < {self.MIN_TRAINING_SAMPLES})")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'Insufficient data after volume filter'}
                    results['summary']['failed'] += 1
                    continue
            else:
                logger.info("  2️⃣ فیلتر حجم فعال نیست")

            # STEP 3: آماده‌سازی داده
            try:
                if target_column not in df_with_features.columns:
                    logger.error(f"  ❌ ستون '{target_column}' پیدا نشد")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': f'Target column "{target_column}" not found'}
                    results['summary']['failed'] += 1
                    continue

                # بررسی features موجود
                available_features = [f for f in self.REQUIRED_FEATURES if f in df_with_features.columns]
                missing_features = [f for f in self.REQUIRED_FEATURES if f not in df_with_features.columns]

                if missing_features:
                    logger.warning(f"  ⚠️ فیچرهای گمشده: {missing_features}")

                if len(available_features) < 3:
                    logger.error(f"  ❌ تعداد فیچرهای معتبر ناکافی: {available_features}")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'Not enough valid features'}
                    results['summary']['failed'] += 1
                    continue

                X = df_with_features[available_features].copy()
                y = df_with_features[target_column]

                X = X.dropna()
                y = y[X.index]

                if len(X) < self.MIN_TRAINING_SAMPLES:
                    logger.error(f"  ❌ نمونه ناکافی ({len(X)} < {self.MIN_TRAINING_SAMPLES})")
                    results['symbols'][symbol] = {'status': 'FAILED', 'reason': 'Insufficient samples'}
                    results['summary']['failed'] += 1
                    continue

                logger.info(f"  ✅ {len(X)} نمونه آماده — features: {available_features}")

                # STEP 4: Train/Test split
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y,
                    test_size=self.DEFAULT_CONFIG['test_size'],
                    random_state=self.DEFAULT_CONFIG['random_state']
                )
                logger.info(f"  4️⃣ Train: {len(X_train)}, Test: {len(X_test)}")

                # STEP 5: Scale
                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                X_test_scaled = scaler.transform(X_test)

                # STEP 6: Train
                logger.info("  6️⃣ Training Random Forest...")
                model = RandomForestClassifier(
                    n_estimators=self.DEFAULT_CONFIG['n_estimators'],
                    max_depth=self.DEFAULT_CONFIG['max_depth'],
                    min_samples_split=self.DEFAULT_CONFIG['min_samples_split'],
                    min_samples_leaf=self.DEFAULT_CONFIG['min_samples_leaf'],
                    random_state=self.DEFAULT_CONFIG['random_state'],
                    n_jobs=-1
                )
                model.fit(X_train_scaled, y_train)

                # STEP 7: Evaluate
                train_score = model.score(X_train_scaled, y_train)
                test_score = model.score(X_test_scaled, y_test)
                logger.info(f"  ✅ Train Accuracy: {train_score:.4f} | Test Accuracy: {test_score:.4f}")

                # STEP 8: ذخیره — نام فایل با _ نه /
                safe_name = self._safe_symbol_name(symbol)
                model_path = self.model_dir / f"{safe_name}_model.pkl"
                scaler_path = self.model_dir / f"{safe_name}_scaler.pkl"

                with open(model_path, 'wb') as f:
                    pickle.dump(model, f)

                with open(scaler_path, 'wb') as f:
                    pickle.dump(scaler, f)

                logger.info(f"  💾 مدل ذخیره شد: {model_path}")
                logger.info(f"  ✅✅✅ {symbol} موفق! ✅✅✅")

                results['symbols'][symbol] = {
                    'status': 'SUCCESS',
                    'model_path': str(model_path),
                    'train_score': float(train_score),
                    'test_score': float(test_score),
                    'samples_used': len(X_train) + len(X_test),
                    'features_used': available_features,
                }
                results['summary']['successful'] += 1

            except Exception as e:
                logger.error(f"  ❌ خطا در training: {str(e)}", exc_info=True)
                results['symbols'][symbol] = {'status': 'FAILED', 'reason': str(e)}
                results['summary']['failed'] += 1

        logger.info("\n" + "=" * 70)
        logger.info(f"✅ نتیجه: {results['summary']['successful']} موفق, {results['summary']['failed']} ناموفق")
        logger.info("=" * 70)

        return results

    def save_results(self, results: Dict, output_path: str = "training_results.json"):
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"📝 نتایج ذخیره شد: {output_path}")


# ─────────────────────────────────────────────
#  MAIN — این بخش قبلاً کامنت بود و اصلاً اجرا نمی‌شد!
# ─────────────────────────────────────────────
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--monthly', action='store_true', help='اجرای بازآموزی ماهانه')
    args = parser.parse_args()

    logger.info("🤖 شروع pipeline آموزش مدل...")

    # مسیر فایل‌های CSV که fetcher.py ذخیره کرده
    # fetcher.py فایل‌ها را در data/4h/BTC_USDT_history.csv ذخیره می‌کند
    data_dir = os.path.join(BASE_DIR, "data", "4h")

    if not os.path.exists(data_dir):
        logger.error(f"❌ پوشه داده پیدا نشد: {data_dir}")
        logger.error("ابتدا fetcher.py را اجرا کنید: python fetcher.py")
        sys.exit(1)

    # لود داده‌ها برای همه ارزهای watchlist
    data_dict = {}

    for symbol in config.WATCHLIST:
        safe_name = symbol.replace("/", "_")
        filepath = os.path.join(data_dir, f"{safe_name}_history.csv")

        if not os.path.exists(filepath):
            logger.warning(f"⚠️ فایل پیدا نشد، رد شد: {filepath}")
            continue

        try:
            df = pd.read_csv(filepath)

            # ستون‌ها را lowercase کن
            df.columns = [c.lower() for c in df.columns]

            # بررسی ستون‌های ضروری
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [c for c in required_cols if c not in df.columns]
            if missing_cols:
                logger.warning(f"⚠️ {symbol}: ستون‌های گمشده {missing_cols} — رد شد")
                continue

            # تبدیل timestamp به datetime اگه موجود باشه
            if 'timestamp' in df.columns:
                df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = df.set_index('datetime')
            elif 'date' in df.columns:
                df['datetime'] = pd.to_datetime(df['date'])
                df = df.set_index('datetime')

            # ساخت target: اگه قیمت کندل بعدی بالاتر بود = 1 (موفق)، وگرنه = 0
            df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
            df = df.dropna()

            if len(df) < 100:
                logger.warning(f"⚠️ {symbol}: فقط {len(df)} ردیف — حداقل 100 نیاز است، رد شد")
                continue

            data_dict[symbol] = df
            logger.info(f"✅ لود شد: {symbol} — {len(df)} ردیف")

        except Exception as e:
            logger.error(f"❌ خطا در لود {symbol}: {e}")
            continue

    if not data_dict:
        logger.error("❌ هیچ داده‌ای لود نشد! ابتدا fetcher.py را اجرا کنید.")
        sys.exit(1)

    logger.info(f"\n📦 {len(data_dict)} ارز آماده آموزش: {list(data_dict.keys())}")

    # مسیر ذخیره مدل‌ها
    models_dir = os.path.join(BASE_DIR, "src", "models")
    trainer = ModelTrainer(model_dir=models_dir)

    # اجرای آموزش
    results = trainer.train_multiple_symbols(
        data_dict,
        target_column='target'
    )

    # ذخیره نتایج
    results_path = os.path.join(BASE_DIR, "training_results.json")
    trainer.save_results(results, results_path)

    # خلاصه نهایی
    successful = results['summary']['successful']
    failed = results['summary']['failed']
    total = results['summary']['total_symbols']

    logger.info(f"\n🎯 نتیجه نهایی: {successful}/{total} مدل با موفقیت ذخیره شد")

    if successful == 0:
        logger.error("❌ هیچ مدلی ذخیره نشد! لاگ‌های بالا را بررسی کنید.")
        sys.exit(1)
    else:
        logger.info(f"✅ فایل‌های pkl در: {models_dir}")
        # لیست فایل‌های ذخیره شده
        for f in os.listdir(models_dir):
            if f.endswith('_model.pkl'):
                size_kb = os.path.getsize(os.path.join(models_dir, f)) / 1024
                logger.info(f"   📄 {f} ({size_kb:.1f} KB)")

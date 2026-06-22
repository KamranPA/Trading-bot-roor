"""
🔧 بهبود شده: train_model.py
مشکل حل شده:
✅ محاسبه تمام ویژگی‌ها قبل از فیلتر حجم
✅ بررسی معتبر بودن داده‌ها قبل از training
✅ بهتر شدن error handling
"""

import pandas as pd
import numpy as np
import pickle
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import json
from datetime import datetime

# فرض: indicators.py در همان دایرکتوری است
from indicators import TechnicalIndicators

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class ModelTrainer:
    """کلاس برای training Random Forest models"""
    
    # پارامترهای پیش‌فرض
    DEFAULT_CONFIG = {
        'test_size': 0.2,
        'random_state': 42,
        'n_estimators': 100,
        'max_depth': 15,
        'min_samples_split': 5,
        'min_samples_leaf': 2,
    }
    
    # حداقل تعداد نمونه برای training
    MIN_TRAINING_SAMPLES = 50
    
    REQUIRED_FEATURES = [
        'ATR', 'EMA_diff', 'RSI', 'MACD', 'ADX',
        'BB_upper', 'BB_lower', 'OBV', 'Volume_SMA'
    ]
    
    def __init__(self, model_dir: str = "./models"):
        """
        Args:
            model_dir: دایرکتوری ذخیره‌سازی models
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        self.models = {}
        self.scalers = {}
    
    def train_multiple_symbols(
        self,
        data_dict: Dict[str, pd.DataFrame],
        volume_threshold: Optional[Dict[str, float]] = None,
        target_column: str = 'target'
    ) -> Dict[str, Dict]:
        """
        Training برای چندین symbol
        
        مهم: ⚠️ ترتیب عملیات CRITICAL:
        1. محاسبه تمام ویژگی‌ها
        2. سپس اعمال فیلتر حجم
        3. سپس training
        
        Args:
            data_dict: Dict[symbol, DataFrame]
            volume_threshold: Dict[symbol, threshold] یا None
            target_column: نام ستون target
            
        Returns:
            Dict with training results
        """
        
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
            logger.info(f"\n📊 در حال پردازش: {symbol}")
            logger.info("-" * 70)
            
            # STEP 1: محاسبه تمام ویژگی‌ها (قبل از هر فیلتر!)
            logger.info(f"  1️⃣ محاسبه اندیکاتورهای تکنیکال...")
            df_with_features, feature_meta = TechnicalIndicators.calculate_all_features(
                df, 
                symbol=symbol,
                min_rows_required=100
            )
            
            if not feature_meta['success']:
                logger.error(
                    f"  ❌ محاسبه ویژگی‌ها ناکام: {feature_meta['missing_features']}"
                )
                results['symbols'][symbol] = {
                    'status': 'FAILED',
                    'reason': 'Feature calculation failed',
                    'details': feature_meta
                }
                results['summary']['failed'] += 1
                continue
            
            logger.info(f"  ✅ {feature_meta['valid_rows']} ردیف معتبر")
            
            # STEP 2: اعمال فیلتر حجم (بعد از محاسبه ویژگی‌ها!)
            if volume_threshold and symbol in volume_threshold:
                vol_thresh = volume_threshold[symbol]
                rows_before = len(df_with_features)
                
                logger.info(f"  2️⃣ اعمال فیلتر حجم (threshold: {vol_thresh:,.0f})...")
                df_with_features = df_with_features[
                    df_with_features['volume'] >= vol_thresh
                ].copy()
                
                rows_after = len(df_with_features)
                logger.info(
                    f"  ✅ {rows_after}/{rows_before} ردیف باقی "
                    f"({rows_before - rows_after} فیلتر شد)"
                )
                
                # بررسی: آیا داده‌های کافی باقی مانده‌اند؟
                if rows_after < self.MIN_TRAINING_SAMPLES:
                    logger.error(
                        f"  ❌ داده‌های ناکافی برای training "
                        f"({rows_after} < {self.MIN_TRAINING_SAMPLES})"
                    )
                    results['symbols'][symbol] = {
                        'status': 'FAILED',
                        'reason': 'Insufficient data after volume filter',
                        'rows_available': rows_after,
                        'rows_required': self.MIN_TRAINING_SAMPLES
                    }
                    results['summary']['failed'] += 1
                    continue
            else:
                logger.info(f"  2️⃣ فیلتر حجم فعال نیست")
            
            # STEP 3: Prepare data برای training
            logger.info(f"  3️⃣ آماده‌سازی داده‌های training...")
            
            try:
                # بررسی وجود target
                if target_column not in df_with_features.columns:
                    logger.error(f"  ❌ ستون '{target_column}' وجود ندارد")
                    results['symbols'][symbol] = {
                        'status': 'FAILED',
                        'reason': f'Target column "{target_column}" not found'
                    }
                    results['summary']['failed'] += 1
                    continue
                
                # جدا کردن features و target
                X = df_with_features[self.REQUIRED_FEATURES]
                y = df_with_features[target_column]
                
                # بررسی: آیا همه features موجود و معتبر هستند؟
                if X.isna().any().any():
                    logger.warning(f"  ⚠️ NaN values in features detected")
                    X = X.dropna()
                    y = y[X.index]
                
                if len(X) < self.MIN_TRAINING_SAMPLES:
                    logger.error(
                        f"  ❌ نمونه‌های ناکافی بعد از validation "
                        f"({len(X)} < {self.MIN_TRAINING_SAMPLES})"
                    )
                    results['symbols'][symbol] = {
                        'status': 'FAILED',
                        'reason': 'Insufficient samples after validation',
                        'samples': len(X)
                    }
                    results['summary']['failed'] += 1
                    continue
                
                logger.info(f"  ✅ {len(X)} نمونه آماده برای training")
                
                # STEP 4: Split train/test
                logger.info(f"  4️⃣ تقسیم داده‌ها (train/test)...")
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y,
                    test_size=self.DEFAULT_CONFIG['test_size'],
                    random_state=self.DEFAULT_CONFIG['random_state']
                )
                
                logger.info(f"  ✅ Train: {len(X_train)}, Test: {len(X_test)}")
                
                # STEP 5: Standardize features
                logger.info(f"  5️⃣ Standardizing features...")
                scaler = StandardScaler()
                X_train_scaled = scaler.fit_transform(X_train)
                X_test_scaled = scaler.transform(X_test)
                
                # STEP 6: Train Random Forest
                logger.info(f"  6️⃣ Training Random Forest model...")
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
                logger.info(f"  7️⃣ ارزیابی مدل...")
                train_score = model.score(X_train_scaled, y_train)
                test_score = model.score(X_test_scaled, y_test)
                
                logger.info(f"  ✅ Train Accuracy: {train_score:.4f}")
                logger.info(f"  ✅ Test Accuracy: {test_score:.4f}")
                
                # Feature importance
                feature_importance = pd.DataFrame({
                    'feature': self.REQUIRED_FEATURES,
                    'importance': model.feature_importances_
                }).sort_values('importance', ascending=False)
                
                logger.info(f"\n  📊 Top 3 features:")
                for idx, row in feature_importance.head(3).iterrows():
                    logger.info(f"     {row['feature']}: {row['importance']:.4f}")
                
                # STEP 8: Save model
                logger.info(f"  8️⃣ ذخیره‌سازی مدل...")
                model_path = self.model_dir / f"{symbol}_model.pkl"
                scaler_path = self.model_dir / f"{symbol}_scaler.pkl"
                
                with open(model_path, 'wb') as f:
                    pickle.dump(model, f)
                
                with open(scaler_path, 'wb') as f:
                    pickle.dump(scaler, f)
                
                logger.info(f"  ✅ مدل ذخیره شد: {model_path}")
                
                # ذخیره‌سازی metadata
                self.models[symbol] = {
                    'path': str(model_path),
                    'scaler_path': str(scaler_path),
                    'train_score': float(train_score),
                    'test_score': float(test_score),
                    'n_features': len(self.REQUIRED_FEATURES),
                    'training_samples': len(X_train),
                    'timestamp': datetime.now().isoformat()
                }
                
                results['symbols'][symbol] = {
                    'status': 'SUCCESS',
                    'model_path': str(model_path),
                    'train_score': float(train_score),
                    'test_score': float(test_score),
                    'samples_used': len(X_train) + len(X_test),
                    'features': self.REQUIRED_FEATURES,
                    'feature_importance': feature_importance.to_dict('records')
                }
                
                results['summary']['successful'] += 1
                
                logger.info(f"  ✅✅✅ {symbol} موفقیت‌آمیز! ✅✅✅")
                
            except Exception as e:
                logger.error(f"  ❌ خطا در training: {str(e)}", exc_info=True)
                results['symbols'][symbol] = {
                    'status': 'FAILED',
                    'reason': 'Training error',
                    'error': str(e)
                }
                results['summary']['failed'] += 1
        
        logger.info("\n" + "=" * 70)
        logger.info(f"✅ نتایج: {results['summary']['successful']} موفق, "
                   f"{results['summary']['failed']} ناموفق")
        logger.info("=" * 70)
        
        return results
    
    def save_results(self, results: Dict, output_path: str = "training_results.json"):
        """ذخیره‌سازی نتایج training"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"📝 نتایج ذخیره شد: {output_path}")


if __name__ == "__main__":
    """
    مثال استفاده:
    """
    
    # load your data
    # data_dict = {
    #     'BTC/USDT': pd.read_csv('btc_data.csv'),
    #     'ETH/USDT': pd.read_csv('eth_data.csv'),
    # }
    
    # تنظیم volume thresholds (اختیاری)
    volume_thresholds = {
        'BTC/USDT': 1000000,  # 1M
        'ETH/USDT': 500000,   # 500K
    }
    
    trainer = ModelTrainer()
    
    # results = trainer.train_multiple_symbols(
    #     data_dict,
    #     volume_threshold=volume_thresholds,
    #     target_column='signal'
    # )
    
    # trainer.save_results(results)

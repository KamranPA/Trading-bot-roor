"""
🔧 بهبود شده: strategy.py
- استفاده صحیح از تمام ویژگی‌های محاسبه شده
- اعمال فیلتر حجم بعد از محاسبه اندیکاتورها
- بهتر شدن signal generation
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

from indicators import TechnicalIndicators

logger = logging.getLogger(__name__)

class TradingStrategy:
    """کلاس برای تولید سیگنال‌های معاملاتی"""
    
    def __init__(self, models_dir: str = "./models"):
        """
        Args:
            models_dir: دایرکتوری models
        """
        self.models_dir = Path(models_dir)
        self.models = {}
        self.scalers = {}
        self.load_models()
    
    def load_models(self):
        """بارگذاری تمام trained models"""
        model_files = list(self.models_dir.glob("*_model.pkl"))
        
        for model_file in model_files:
            symbol = model_file.stem.replace("_model", "")
            scaler_file = self.models_dir / f"{symbol}_scaler.pkl"
            
            try:
                with open(model_file, 'rb') as f:
                    self.models[symbol] = pickle.load(f)
                
                with open(scaler_file, 'rb') as f:
                    self.scalers[symbol] = pickle.load(f)
                
                logger.info(f"✅ مدل بارگذاری شد: {symbol}")
            except Exception as e:
                logger.error(f"❌ خطا در بارگذاری {symbol}: {str(e)}")
    
    def generate_signals(
        self,
        data_dict: Dict[str, pd.DataFrame],
        volume_threshold: Optional[Dict[str, float]] = None,
        model_confidence: float = 0.6
    ) -> Dict[str, pd.DataFrame]:
        """
        تولید سیگنال‌های معاملاتی برای چندین symbol
        
        ⚠️ مهم: ترتیب عملیات:
        1. محاسبه تمام ویژگی‌ها
        2. اعمال فیلتر حجم
        3. اعمال مدل ML
        4. تولید سیگنال
        
        Args:
            data_dict: Dict[symbol, DataFrame]
            volume_threshold: آستانه حجم
            model_confidence: حداقل confidence برای سیگنال
            
        Returns:
            Dict[symbol, DataFrame with signals]
        """
        
        results = {}
        
        for symbol, df in data_dict.items():
            logger.info(f"\n📊 تولید سیگنال برای: {symbol}")
            logger.info("-" * 70)
            
            # STEP 1: محاسبه ویژگی‌ها
            logger.info(f"  1️⃣ محاسبه اندیکاتورها...")
            df_features, meta = TechnicalIndicators.calculate_all_features(
                df,
                symbol=symbol
            )
            
            if not meta['success']:
                logger.error(f"  ❌ محاسبه ویژگی‌ها ناموفق")
                results[symbol] = pd.DataFrame()
                continue
            
            # STEP 2: اعمال فیلتر حجم (بعد از محاسبه!)
            if volume_threshold and symbol in volume_threshold:
                vol_thresh = volume_threshold[symbol]
                logger.info(f"  2️⃣ اعمال فیلتر حجم ({vol_thresh:,.0f})...")
                
                rows_before = len(df_features)
                df_features = df_features[
                    df_features['volume'] >= vol_thresh
                ].copy()
                
                logger.info(f"  ✅ {len(df_features)}/{rows_before} ردیف")
            
            # STEP 3: حذف NaN values
            logger.info(f"  3️⃣ تمیز‌سازی داده‌ها...")
            df_clean = df_features.dropna()
            logger.info(f"  ✅ {len(df_clean)} ردیف معتبر")
            
            if len(df_clean) == 0:
                logger.warning(f"  ⚠️ هیچ داده معتبری وجود ندارد")
                results[symbol] = pd.DataFrame()
                continue
            
            # STEP 4: اعمال مدل ML
            if symbol not in self.models:
                logger.warning(f"  ⚠️ مدل برای {symbol} وجود ندارد")
                results[symbol] = df_clean
                continue
            
            logger.info(f"  4️⃣ اعمال مدل ML...")
            
            required_features = [
                'ATR', 'EMA_diff', 'RSI', 'MACD', 'ADX',
                'BB_upper', 'BB_lower', 'OBV', 'Volume_SMA'
            ]
            
            X = df_clean[required_features].values
            X_scaled = self.scalers[symbol].transform(X)
            
            # پیش‌بینی احتمالات
            model = self.models[symbol]
            probabilities = model.predict_proba(X_scaled)
            predictions = model.predict(X_scaled)
            
            # confidence = احتمال پیش‌بینی شده
            confidence = np.max(probabilities, axis=1)
            
            # STEP 5: تولید سیگنال‌ها
            logger.info(f"  5️⃣ تولید سیگنال‌ها...")
            
            df_clean['ml_signal'] = predictions
            df_clean['confidence'] = confidence
            
            # تولید سیگنال نهایی (با confidence filter)
            df_clean['signal'] = np.where(
                confidence >= model_confidence,
                predictions,
                0  # حداقل confidence
            )
            
            # STEP 6: تحلیل سیگنال‌ها
            buy_signals = (df_clean['signal'] == 1).sum()
            sell_signals = (df_clean['signal'] == -1).sum()
            no_signals = (df_clean['signal'] == 0).sum()
            
            avg_confidence = confidence.mean()
            
            logger.info(f"  ✅ سیگنال‌های تولید شده:")
            logger.info(f"     خرید: {buy_signals}")
            logger.info(f"     فروش: {sell_signals}")
            logger.info(f"     بدون سیگنال: {no_signals}")
            logger.info(f"     Confidence متوسط: {avg_confidence:.4f}")
            
            results[symbol] = df_clean
            
            logger.info(f"  ✅ {symbol} تکمیل شد")
        
        return results
    
    def get_trading_rules(
        self,
        symbol_data: pd.DataFrame,
        symbol: str = "UNKNOWN"
    ) -> Dict:
        """
        قوانین معاملاتی اضافی بر اساس اندیکاتورها
        
        Returns:
            Dict با توصیات تردید
        """
        
        if len(symbol_data) == 0:
            return {'recommendation': 'NO_DATA'}
        
        latest = symbol_data.iloc[-1]
        
        rules = {
            'symbol': symbol,
            'timestamp': symbol_data.index[-1] if hasattr(symbol_data.index[-1], '__str__') else None,
            'recommendation': 'HOLD',
            'reasons': []
        }
        
        # Rule 1: Trend Check (ADX)
        if latest['ADX'] > 25:
            rules['reasons'].append(f"قوی Trend (ADX={latest['ADX']:.2f})")
            if latest['EMA_diff'] > 0:
                rules['recommendation'] = 'BUY'
            else:
                rules['recommendation'] = 'SELL'
        else:
            rules['reasons'].append("Trend ضعیف")
        
        # Rule 2: Momentum Check (RSI)
        if latest['RSI'] > 70:
            rules['reasons'].append("Overbought (RSI > 70)")
            if rules['recommendation'] == 'BUY':
                rules['recommendation'] = 'WAIT'
        elif latest['RSI'] < 30:
            rules['reasons'].append("Oversold (RSI < 30)")
            if rules['recommendation'] == 'SELL':
                rules['recommendation'] = 'WAIT'
        
        # Rule 3: Volatility Check (ATR)
        atr_threshold = latest['close'] * 0.02  # 2% از قیمت
        if latest['ATR'] > atr_threshold:
            rules['reasons'].append("Volatility بالا")
        else:
            rules['reasons'].append("Volatility پایین")
        
        # Rule 4: Volume Check
        vol_sma = latest['Volume_SMA']
        if latest['volume'] > vol_sma * 1.5:
            rules['reasons'].append("حجم بالای متوسط")
        elif latest['volume'] < vol_sma * 0.5:
            rules['reasons'].append("حجم پایین")
        
        # Rule 5: Bollinger Bands
        bb_range = latest['BB_upper'] - latest['BB_lower']
        if latest['close'] > latest['BB_upper']:
            rules['reasons'].append("قیمت بالای BB upper")
        elif latest['close'] < latest['BB_lower']:
            rules['reasons'].append("قیمت پایین BB lower")
        
        return rules


def create_signal_summary(
    signals_dict: Dict[str, pd.DataFrame],
    output_file: str = "trading_signals.csv"
) -> pd.DataFrame:
    """
    خلاصه‌ای از تمام سیگنال‌ها
    """
    
    summary_rows = []
    
    for symbol, df in signals_dict.items():
        if len(df) == 0:
            continue
        
        latest = df.iloc[-1]
        
        summary_rows.append({
            'symbol': symbol,
            'timestamp': df.index[-1] if hasattr(df.index[-1], '__str__') else None,
            'close': latest.get('close', np.nan),
            'signal': latest.get('signal', 0),
            'confidence': latest.get('confidence', 0),
            'RSI': latest.get('RSI', np.nan),
            'ADX': latest.get('ADX', np.nan),
            'volume': latest.get('volume', 0),
            'ATR': latest.get('ATR', np.nan),
        })
    
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(output_file, index=False)
    logger.info(f"📝 خلاصه سیگنال‌ها ذخیره شد: {output_file}")
    
    return summary_df

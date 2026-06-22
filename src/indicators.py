"""
🔧 بهبود شده: indicators.py
- محاسبه تمام ویژگی‌ها قبل از اعمال فیلتر حجم
- اضافه کردن handling برای empty/None values
- بهتر شدن error messages
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """کلاس برای محاسبه تمام اندیکاتورهای تکنیکال مورد نیاز"""
    
    # تنظیمات پنجره برای اندیکاتورها
    INDICATOR_WINDOWS = {
        'atr_period': 14,
        'ema_short': 12,
        'ema_long': 26,
        'rsi_period': 14,
        'adx_period': 14,
    }
    
    @staticmethod
    def calculate_all_features(
        df: pd.DataFrame, 
        symbol: str = "UNKNOWN",
        min_rows_required: int = 30
    ) -> Tuple[pd.DataFrame, Dict[str, any]]:
        """
        محاسبه تمام ویژگی‌های مورد نیاز برای مدل ML
        
        Args:
            df: DataFrame حاوی OHLCV data
            symbol: نام جفت ارز (برای logging)
            min_rows_required: حداقل تعداد ردیف‌های مورد نیاز
            
        Returns:
            Tuple[df_with_features, metadata]
        """
        
        metadata = {
            'symbol': symbol,
            'total_rows': len(df),
            'missing_features': [],
            'success': True
        }
        
        # اگر داده‌های ناکافی باشند
        if len(df) < min_rows_required:
            metadata['success'] = False
            metadata['missing_features'] = ['INSUFFICIENT_DATA']
            logger.warning(
                f"⚠️ {symbol}: فقط {len(df)} ردیف وجود دارد "
                f"(حداقل مورد نیاز: {min_rows_required})"
            )
            return df, metadata
        
        try:
            # نقل DataFrame برای جلوگیری از تغییرات در اصل
            df = df.copy()
            
            # 1️⃣ ATR (Average True Range)
            df = TechnicalIndicators._calculate_atr(df, symbol)
            
            # 2️⃣ EMA (Exponential Moving Averages)
            df = TechnicalIndicators._calculate_ema(df, symbol)
            
            # 3️⃣ RSI (Relative Strength Index)
            df = TechnicalIndicators._calculate_rsi(df, symbol)
            
            # 4️⃣ MACD (Moving Average Convergence Divergence)
            df = TechnicalIndicators._calculate_macd(df, symbol)
            
            # 5️⃣ ADX (Average Directional Index)
            df = TechnicalIndicators._calculate_adx(df, symbol)
            
            # 6️⃣ Bollinger Bands
            df = TechnicalIndicators._calculate_bollinger_bands(df, symbol)
            
            # 7️⃣ Volume Indicators
            df = TechnicalIndicators._calculate_volume_indicators(df, symbol)
            
            # ✅ بررسی ویژگی‌های الزامی
            required_features = [
                'ATR', 'EMA_diff', 'RSI', 'MACD', 'ADX',
                'BB_upper', 'BB_lower', 'OBV', 'Volume_SMA'
            ]
            
            missing = []
            for feat in required_features:
                if feat not in df.columns:
                    missing.append(feat)
                elif df[feat].isna().all():
                    missing.append(f"{feat}_ALL_NAN")
            
            if missing:
                metadata['missing_features'] = missing
                metadata['success'] = False
                logger.warning(
                    f"⚠️ {symbol}: ویژگی‌های گمشده: {missing}"
                )
            else:
                # حذف ردیف‌های شامل NaN
                rows_before = len(df)
                df = df.dropna()
                rows_after = len(df)
                
                if rows_after == 0:
                    metadata['success'] = False
                    metadata['missing_features'] = ['ALL_NAN_AFTER_CALCULATION']
                    logger.warning(
                        f"❌ {symbol}: تمام ردیف‌ها بعد از محاسبه NaN هستند"
                    )
                else:
                    logger.info(
                        f"✅ {symbol}: {rows_after}/{rows_before} ردیف معتبر "
                        f"({rows_before - rows_after} ردیف حذف شد)"
                    )
                    metadata['valid_rows'] = rows_after
            
            return df, metadata
            
        except Exception as e:
            logger.error(f"❌ {symbol}: خطا در محاسبه اندیکاتورها: {str(e)}")
            metadata['success'] = False
            metadata['error'] = str(e)
            return df, metadata
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """محاسبه ATR"""
        period = TechnicalIndicators.INDICATOR_WINDOWS['atr_period']
        
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        
        df['ATR'] = true_range.rolling(window=period).mean()
        return df
    
    @staticmethod
    def _calculate_ema(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """محاسبه EMA و تفاوت آن"""
        short = TechnicalIndicators.INDICATOR_WINDOWS['ema_short']
        long = TechnicalIndicators.INDICATOR_WINDOWS['ema_long']
        
        df['EMA_short'] = df['close'].ewm(span=short, adjust=False).mean()
        df['EMA_long'] = df['close'].ewm(span=long, adjust=False).mean()
        df['EMA_diff'] = df['EMA_short'] - df['EMA_long']
        
        return df
    
    @staticmethod
    def _calculate_rsi(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """محاسبه RSI"""
        period = TechnicalIndicators.INDICATOR_WINDOWS['rsi_period']
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss.replace(0, 1)
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df
    
    @staticmethod
    def _calculate_macd(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """محاسبه MACD"""
        short = TechnicalIndicators.INDICATOR_WINDOWS['ema_short']
        long = TechnicalIndicators.INDICATOR_WINDOWS['ema_long']
        signal = 9
        
        ema_short = df['close'].ewm(span=short, adjust=False).mean()
        ema_long = df['close'].ewm(span=long, adjust=False).mean()
        
        df['MACD'] = ema_short - ema_long
        df['MACD_signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
        df['MACD_histogram'] = df['MACD'] - df['MACD_signal']
        
        return df
    
    @staticmethod
    def _calculate_adx(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """محاسبه ADX"""
        period = TechnicalIndicators.INDICATOR_WINDOWS['adx_period']
        
        high_diff = df['high'].diff()
        low_diff = -df['low'].diff()
        
        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
        
        tr = TechnicalIndicators._calculate_true_range(df)
        
        plus_di = 100 * (plus_dm.rolling(period).mean() / tr.rolling(period).mean())
        minus_di = 100 * (minus_dm.rolling(period).mean() / tr.rolling(period).mean())
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        df['ADX'] = dx.rolling(period).mean()
        
        return df
    
    @staticmethod
    def _calculate_bollinger_bands(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """محاسبه Bollinger Bands"""
        period = 20
        std_dev = 2
        
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        
        df['BB_upper'] = sma + (std * std_dev)
        df['BB_lower'] = sma - (std * std_dev)
        df['BB_middle'] = sma
        
        return df
    
    @staticmethod
    def _calculate_volume_indicators(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """محاسبه Volume Indicators"""
        if 'volume' not in df.columns:
            logger.warning(f"⚠️ {symbol}: ستون 'volume' وجود ندارد")
            df['OBV'] = 0
            df['Volume_SMA'] = 0
            return df
        
        # OBV (On Balance Volume)
        df['OBV'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        
        # Volume SMA
        df['Volume_SMA'] = df['volume'].rolling(window=20).mean()
        
        return df
    
    @staticmethod
    def _calculate_true_range(df: pd.DataFrame) -> pd.Series:
        """محاسبه کمکی True Range"""
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        return ranges.max(axis=1)
    
    @staticmethod
    def validate_features(df: pd.DataFrame, symbol: str = "UNKNOWN") -> bool:
        """بررسی صحت تمام ویژگی‌ها"""
        required = [
            'ATR', 'EMA_diff', 'RSI', 'MACD', 'ADX',
            'BB_upper', 'BB_lower', 'OBV', 'Volume_SMA'
        ]
        
        missing = [f for f in required if f not in df.columns]
        
        if missing:
            logger.error(f"❌ {symbol}: ویژگی‌های گمشده: {missing}")
            return False
        
        nan_counts = df[required].isna().sum()
        if nan_counts.any():
            logger.warning(f"⚠️ {symbol}: NaN values found: {nan_counts[nan_counts > 0].to_dict()}")
        
        return True

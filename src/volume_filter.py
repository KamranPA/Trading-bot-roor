"""
FILE PATH: src/volume_filter.py  (v1.0 - Dynamic Volume Filter)
ماژول مشترک فیلتر حجم پویا — استفاده در:
  strategy.py, backtester.py, optimizer.py, train_model.py

منطق: volume >= Volume_SMA_20 * VOLUME_MULTIPLIER
  - به جای عدد ثابت، از میانگین متحرک خود داده استفاده می‌شود
  - با هر ارز و هر دوره زمانی خودکار تنظیم می‌شود
  - VOLUME_MULTIPLIER = 0.5 (پیشنهاد بهینه)
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

try:
    import config
    VOLUME_MULTIPLIER = float(getattr(config, 'VOLUME_MULTIPLIER', 0.5))
    ENABLE_VOLUME_FILTER = getattr(config, 'ENABLE_VOLUME_FILTER', True)
except ImportError:
    VOLUME_MULTIPLIER    = 0.5
    ENABLE_VOLUME_FILTER = True

VOLUME_SMA_WINDOW = 20   # یکسان با indicators.py


def passes_volume_filter(
    row: pd.Series,
    symbol: str = "UNKNOWN",
    multiplier: float = None,
) -> bool:
    """
    بررسی فیلتر حجم پویا برای یک کندل.

    منطق:
      volume >= Volume_SMA_20 * multiplier

    اگر Volume_SMA موجود نباشد (مثلاً اولین 20 کندل)، فیلتر رد نمی‌کند.

    Args:
        row: یک ردیف DataFrame (pd.Series)
        symbol: نام ارز برای لاگ
        multiplier: ضریب (پیش‌فرض از config)

    Returns:
        True  اگر حجم کافی است یا فیلتر غیرفعال است
        False اگر حجم ناکافی است
    """
    if not ENABLE_VOLUME_FILTER:
        return True

    m = multiplier if multiplier is not None else VOLUME_MULTIPLIER

    # خواندن حجم فعلی
    vol = row.get('volume', row.get('Volume', None))
    if vol is None or pd.isna(vol):
        return True   # اگر حجم نداریم، فیلتر نمی‌کنیم

    try:
        current_vol = float(vol)
    except (TypeError, ValueError):
        return True

    # خواندن Volume_SMA (از indicators.py محاسبه شده)
    sma = row.get('Volume_SMA', row.get('volume_sma', None))

    if sma is None or pd.isna(sma) or float(sma) <= 0:
        # SMA موجود نیست → فیلتر نمی‌کنیم
        return True

    threshold = float(sma) * m

    if current_vol < threshold:
        logger.debug(
            f"{symbol}: حجم {current_vol:,.0f} < "
            f"SMA×{m} ({threshold:,.0f}) — رد شد"
        )
        return False

    return True


def apply_volume_filter_df(
    df: pd.DataFrame,
    symbol: str = "UNKNOWN",
    multiplier: float = None,
) -> pd.DataFrame:
    """
    اعمال فیلتر حجم پویا روی کل DataFrame.
    برای training استفاده می‌شود.

    اگر Volume_SMA در df نباشد، آن را محاسبه می‌کند.
    """
    if not ENABLE_VOLUME_FILTER:
        return df

    m = multiplier if multiplier is not None else VOLUME_MULTIPLIER

    vol_col = 'volume' if 'volume' in df.columns else 'Volume'
    if vol_col not in df.columns:
        logger.warning(f"{symbol}: ستون حجم وجود ندارد — فیلتر اعمال نشد")
        return df

    # محاسبه Volume_SMA اگر موجود نباشد
    if 'Volume_SMA' not in df.columns:
        df = df.copy()
        df['Volume_SMA'] = df[vol_col].rolling(window=VOLUME_SMA_WINDOW, min_periods=1).mean()

    threshold    = df['Volume_SMA'] * m
    mask         = df[vol_col] >= threshold
    rows_before  = len(df)
    df_filtered  = df[mask].copy()
    rows_after   = len(df_filtered)

    if rows_before > 0:
        pct = rows_after / rows_before * 100
        logger.info(
            f"{symbol}: فیلتر حجم پویا (×{m}): "
            f"{rows_after}/{rows_before} ({pct:.1f}%) کندل باقی ماند"
        )

    if rows_after == 0:
        logger.warning(f"{symbol}: فیلتر حجم همه ردیف‌ها را حذف کرد — برمی‌گردیم")
        return df  # بدون فیلتر برمی‌گردیم

    return df_filtered

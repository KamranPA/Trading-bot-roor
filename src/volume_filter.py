"""
FILE PATH: src/volume_filter.py  (v1.1 - Fixed)
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

try:
    import config
    VOLUME_MULTIPLIER    = float(getattr(config, 'VOLUME_MULTIPLIER', 0.5))
    ENABLE_VOLUME_FILTER = getattr(config, 'ENABLE_VOLUME_FILTER', True)
except ImportError:
    VOLUME_MULTIPLIER    = 0.5
    ENABLE_VOLUME_FILTER = True

VOLUME_SMA_WINDOW = 20


def passes_volume_filter(
    row: pd.Series,
    symbol: str = "UNKNOWN",
    multiplier: float = None,
) -> bool:
    if not ENABLE_VOLUME_FILTER:
        return True

    m = multiplier if multiplier is not None else VOLUME_MULTIPLIER

    # خواندن حجم — همه حالت‌های ممکن
    vol = None
    for key in ('volume', 'Volume', 'VOLUME'):
        v = row.get(key, None)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            vol = v
            break

    if vol is None:
        return True  # ستون حجم نداریم → فیلتر نمی‌کنیم

    try:
        current_vol = float(vol)
    except (TypeError, ValueError):
        return True

    if current_vol <= 0:
        return True

    # خواندن Volume_SMA — همه حالت‌های ممکن
    sma = None
    for key in ('Volume_SMA', 'volume_sma', 'volume_sma20', 'Volume_SMA_20'):
        v = row.get(key, None)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            sma = v
            break

    if sma is None or float(sma) <= 0:
        return True  # SMA نداریم → فیلتر نمی‌کنیم

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
    if not ENABLE_VOLUME_FILTER:
        return df

    m = multiplier if multiplier is not None else VOLUME_MULTIPLIER

    vol_col = None
    for c in ('volume', 'Volume', 'VOLUME'):
        if c in df.columns:
            vol_col = c
            break

    if vol_col is None:
        logger.warning(f"{symbol}: ستون حجم وجود ندارد — فیلتر اعمال نشد")
        return df

    sma_col = None
    for c in ('Volume_SMA', 'volume_sma', 'volume_sma20', 'Volume_SMA_20'):
        if c in df.columns:
            sma_col = c
            break

    if sma_col is None:
        df = df.copy()
        df['Volume_SMA'] = df[vol_col].rolling(window=VOLUME_SMA_WINDOW, min_periods=1).mean()
        sma_col = 'Volume_SMA'

    threshold   = df[sma_col] * m
    mask        = df[vol_col] >= threshold
    rows_before = len(df)
    df_filtered = df[mask].copy()
    rows_after  = len(df_filtered)

    if rows_before > 0:
        pct = rows_after / rows_before * 100
        logger.info(
            f"{symbol}: فیلتر حجم پویا (×{m}): "
            f"{rows_after}/{rows_before} ({pct:.1f}%) کندل باقی ماند"
        )

    if rows_after == 0:
        logger.warning(f"{symbol}: فیلتر حجم همه ردیف‌ها را حذف کرد — برمی‌گردیم")
        return df

    return df_filtered

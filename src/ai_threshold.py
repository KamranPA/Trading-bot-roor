"""
FILE PATH: src/ai_threshold.py (v1.0)
ماژول مشترک خواندن AI_THRESHOLD per-symbol — استفاده در:
  strategy.py (لایو), backtester.py, optimizer.py

منطق:
  - فایل ai_thresholds.json (ساخته‌شده توسط train_model.py) را می‌خواند
  - برای هر symbol، اگر threshold کالیبره‌شده موجود باشد همان را برمی‌گرداند
  - در غیر این صورت fallback به config.AI_THRESHOLD ثابت
"""

import os
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AI_THRESHOLDS_FILE = os.path.join(BASE_DIR, 'ai_thresholds.json')

_cache: Optional[Dict] = None
_cache_mtime: Optional[float] = None


def _load_thresholds() -> Dict:
    """
    لود فایل ai_thresholds.json با کش بر اساس mtime
    (اگر فایل عوض شد، دوباره خوانده می‌شود — مفید برای اجرای طولانی optimizer)
    """
    global _cache, _cache_mtime

    if not os.path.exists(AI_THRESHOLDS_FILE):
        return {}

    try:
        mtime = os.path.getmtime(AI_THRESHOLDS_FILE)
    except OSError:
        return {}

    if _cache is not None and _cache_mtime == mtime:
        return _cache

    try:
        with open(AI_THRESHOLDS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _cache = data
        _cache_mtime = mtime
        return data
    except Exception as e:
        logger.warning(f"⚠️ خطا در خواندن ai_thresholds.json: {e}")
        return {}


def get_ai_threshold(symbol: str, default: float = 65.0) -> float:
    """
    دریافت AI_THRESHOLD per-symbol.

    Args:
        symbol: می‌تواند 'BTCUSDT' یا 'BTC/USDT' باشد — هر دو نرمال می‌شوند
        default: مقدار fallback اگر کالیبراسیون موجود نباشد (معمولاً config.AI_THRESHOLD)

    Returns:
        threshold عددی (0-100)
    """
    brain_symbol = symbol
    if '/' not in symbol and 'USDT' in symbol:
        base = symbol.replace('USDT', '')
        brain_symbol = f"{base}/USDT"

    data = _load_thresholds()
    entry = data.get(brain_symbol)

    if entry and isinstance(entry, dict) and 'threshold' in entry:
        return float(entry['threshold'])

    return float(default)


def get_threshold_info(symbol: str) -> Optional[Dict]:
    """برگرداندن کل اطلاعات کالیبراسیون (برای لاگ/دیباگ) یا None اگر موجود نباشد"""
    brain_symbol = symbol
    if '/' not in symbol and 'USDT' in symbol:
        base = symbol.replace('USDT', '')
        brain_symbol = f"{base}/USDT"

    data = _load_thresholds()
    return data.get(brain_symbol)

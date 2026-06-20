# ---------------------------------------------------------
# FILE PATH: src/train_model.py (v10.0 - Backtest-First Training)
# تغییرات نسبت به نسخه قبلی:
#   1. اولویت آموزش: بکتست → لایو (جبران کم‌بود داده لایو)
#   2. ادغام داده‌های بکتست CSV با داده‌های لایو PostgreSQL
#   3. فیلتر صحیح وضعیت: SL_HIT، TP_HIT و CLOSED همه دیده می‌شن
#   4. حداقل نمونه‌ها از ۱۰ به ۳۰ افزایش یافت برای مدل قوی‌تر
# ---------------------------------------------------------
import pandas as pd
import numpy as np
import os
import sys
import joblib
import logging

try:
    from lightgbm import LGBMClassifier
except ImportError:
    print("CRITICAL: LightGBM is not installed.")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config

logger = logging.getLogger(__name__)

FEATURES      = list(config.AI_FEATURES)
MIN_SAMPLES   = 30   # حداقل نمونه برای آموزش معنادار
BACKTEST_CSV  = os.path.join(BASE_DIR, 'data', 'backtest_trades.csv')


# ---------------------------------------------------------------------------
# منابع داده
# ---------------------------------------------------------------------------

def _load_backtest_data(symbol: str) -> pd.DataFrame:
    """خواندن معاملات بسته‌شده از فایل CSV بکتست."""
    if not os.path.exists(BACKTEST_CSV):
        return pd.DataFrame()
    try:
        df = pd.read_csv(BACKTEST_CSV, encoding='utf-8')
        df = df[df['pair'] == symbol].copy()
        df = df[df['status'].isin(['SL_HIT', 'TP_HIT', 'EXPIRED', 'CLOSED'])].copy()
        df = df.dropna(subset=['pnl_percent'])
        logger.info("بکتست %s: %d معامله بارگذاری شد", symbol, len(df))
        return df
    except Exception as e:
        logger.error("خطا در خواندن CSV بکتست برای %s: %s", symbol, e)
        return pd.DataFrame()


def _load_live_data(symbol: str) -> pd.DataFrame:
    """خواندن معاملات بسته‌شده از PostgreSQL (داده لایو)."""
    try:
        from src import database
        query = """
            SELECT * FROM signals
            WHERE pair = %s
              AND status IN ('CLOSED', 'SL_HIT', 'TP_HIT')
              AND pnl_percent IS NOT NULL
        """
        with database.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=(symbol,))
        df.columns = [c.lower() for c in df.columns]
        logger.info("لایو %s: %d معامله بارگذاری شد", symbol, len(df))
        return df
    except Exception as e:
        logger.warning("خواندن داده لایو برای %s ناموفق: %s", symbol, e)
        return pd.DataFrame()


def _merge_sources(bt_df: pd.DataFrame, live_df: pd.DataFrame) -> pd.DataFrame:
    """
    ادغام داده‌های بکتست و لایو.
    - بکتست: منبع اصلی (حجم بالا)
    - لایو: تکمیل‌کننده (رفتار واقعی بازار)
    تکراری‌ها بر اساس entry_time + pair حذف می‌شن.
    """
    frames = []
    if not bt_df.empty:
        bt_df = bt_df.copy()
        bt_df['source'] = 'backtest'
        frames.append(bt_df)
    if not live_df.empty:
        live_df = live_df.copy()
        live_df['source'] = 'live'
        frames.append(live_df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # اولویت لایو در صورت تکرار زمانی
    if 'entry_time' in combined.columns:
        combined = combined.sort_values('source', ascending=False)
        combined = combined.drop_duplicates(subset=['pair', 'entry_time'], keep='first')

    return combined.reset_index(drop=True)


# ---------------------------------------------------------------------------
# آموزش مدل
# ---------------------------------------------------------------------------

def train_model_for_symbol(symbol: str) -> bool:
    """
    آموزش مدل AI برای یک ارز.
    منبع اصلی: بکتست CSV — منبع ثانویه: لایو PostgreSQL.

    Returns:
        True در صورت موفقیت
    """
    # ۱. جمع‌آوری داده از هر دو منبع
    bt_df   = _load_backtest_data(symbol)
    live_df = _load_live_data(symbol)
    df      = _merge_sources(bt_df, live_df)

    if df.empty:
        logger.warning("⚠️ هیچ داده‌ای برای %s یافت نشد (نه بکتست، نه لایو).", symbol)
        return False

    # ۲. بررسی وجود همه فیچرها
    missing = [f for f in FEATURES if f not in df.columns]
    if missing:
        logger.warning("⚠️ فیچرهای ناموجود برای %s: %s", symbol, missing)
        return False

    # ۳. ساخت برچسب هدف (۱=سود، ۰=ضرر)
    df['target_label'] = np.where(df['pnl_percent'] > 0, 1, 0)
    df = df.dropna(subset=FEATURES + ['target_label'])

    if df['target_label'].nunique() < 2:
        logger.warning(
            "⚠️ %s: همه %d معامله یک‌طرفه هستند (همه سود یا همه ضرر). "
            "مدل آموزش نمی‌بیند.",
            symbol, len(df)
        )
        return False

    if len(df) < MIN_SAMPLES:
        logger.warning(
            "⚠️ %s: فقط %d نمونه موجود است (حداقل %d لازم است).",
            symbol, len(df), MIN_SAMPLES
        )
        return False

    # ۴. مرتب‌سازی زمانی
    time_col = next((c for c in ['entry_time', 'timestamp'] if c in df.columns), None)
    if time_col:
        df = df.sort_values(by=time_col, ascending=True)
    df = df.reset_index(drop=True)

    X = df[FEATURES]
    y = df['target_label'].to_numpy()

    # ۵. تقسیم train/test (80/20)
    split_idx        = max(int(len(X) * 0.8), 1)
    X_train, X_test  = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test  = y[:split_idx], y[split_idx:]

    # ۶. آموزش LightGBM
    model = LGBMClassifier(
        n_estimators=200,
        learning_rate=0.02,
        max_depth=5,
        num_leaves=20,
        min_child_samples=10,
        subsample=0.8,
        colsample_bytree=0.8,
        class_weight='balanced',
        random_state=42,
        n_jobs=1,
        verbose=-1,
    )

    if len(np.unique(y_test)) < 2:
        model.fit(X_train, y_train)
    else:
        model.fit(X_train, y_train, eval_set=[(X_test, y_test)])

    # ۷. ذخیره مدل
    safe_name  = symbol.replace('/', '_')
    models_dir = os.path.join(BASE_DIR, 'src', 'models')
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, f"{safe_name}_model.pkl")
    joblib.dump(model, model_path)

    wins  = int(y.sum())
    total = len(y)
    logger.info(
        "✅ مدل %s آموزش دید | نمونه: %d (بکتست: %d + لایو: %d) | Win Rate داده: %.1f%%",
        symbol, total, len(bt_df), len(live_df), wins / total * 100
    )
    print(
        f"🎯 مدل {symbol} آموزش دید | "
        f"نمونه: {total} (بکتست: {len(bt_df)} + لایو: {len(live_df)}) | "
        f"Win Rate داده: {wins/total*100:.1f}%"
    )
    return True


def train_all() -> None:
    """آموزش مدل برای تمام ارزهای WATCHLIST."""
    success, failed = [], []
    for symbol in config.WATCHLIST:
        ok = train_model_for_symbol(symbol)
        (success if ok else failed).append(symbol)

    print(f"\n📊 نتیجه آموزش:")
    print(f"   ✅ موفق  ({len(success)}): {', '.join(success) or '-'}")
    print(f"   ❌ ناموفق ({len(failed)}): {', '.join(failed) or '-'}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    )
    train_all()

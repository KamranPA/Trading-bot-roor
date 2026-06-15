# ---------------------------------------------------------
# FILE PATH: src/train_model.py (v8.3 - Fixed Time-Series Data Leakage)
# ---------------------------------------------------------
import sqlite3
import pandas as pd
import numpy as np
import os
import sys
import joblib
import logging

try:
    from lightgbm import LGBMClassifier
except ImportError:
    print("CRITICAL: LightGBM is not installed. Run 'pip install lightgbm'")
    sys.exit(1)

# تنظیم مسیر پایه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config

def get_data_from_db(db_path, symbol):
    """استخراج امن دیتا از دیتابیس"""
    if not os.path.exists(db_path):
        return pd.DataFrame()
    try:
        with sqlite3.connect(db_path) as conn:
            return pd.read_sql_query(
                "SELECT * FROM signals WHERE symbol = ? AND status = 'CLOSED'", 
                conn, params=(symbol,)
            )
    except Exception as e:
        print(f"❌ خطای دیتابیس در {db_path}: {e}")
        return pd.DataFrame()

def train_model_for_symbol(symbol, mode="backtest"):
    df = pd.DataFrame()
    
    # --- ۱. تجمیع داده‌ها ---
    if mode == "monthly":
        df_backtest = get_data_from_db(config.DB_PATH_BACKTEST, symbol)
        df_live = get_data_from_db(config.DB_PATH_LIVE, symbol)
        df = pd.concat([df_backtest, df_live], ignore_index=True)
    else:
        df = get_data_from_db(config.DB_PATH_BACKTEST, symbol)

    if df.empty:
        print(f"⚠️ دیتایی برای {symbol} یافت نشد.")
        return

    # --- ۲. پیش‌پردازش کامل ---
    features = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
        'feat_body_ratio', 'feat_high_volume_session'
    ]
    
    df = df.dropna(subset=features)
    
    # ⚠️ بسیار مهم: ابتدا داده‌ها را بر اساس زمان صعودی مرتب می‌کنیم تا توالی زمانی حفظ شود
    df = df.sort_values(by='timestamp', ascending=True)
    df = df.drop_duplicates(subset=['timestamp'])
    
    if len(df) < 50:
        print(f"⚠️ معاملات کافی برای ارتقای {symbol} نیست ({len(df)}).")
        return

    X = df[features]
    y = np.where(df['pnl_percent'] > 0, 1, 0)

    # --- ۳. تقسیم داده‌ها بدون Shuffle برای جلوگیری از نشت داده (Time-Series Split) ---
    # ۸۰ درصد ابتدایی داده‌ها (گذشته) برای آموزش و ۲۰ درصد انتهایی (آینده) برای تست فیلتر می‌شوند
    split_idx = int(len(df) * 0.8)
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    # --- ۴. آموزش مدل LightGBM ---
    model = LGBMClassifier(
        n_estimators=100,       # برای جلوگیری از Overfit روی داده‌های محدود کمی کاهش یافت
        learning_rate=0.03,      # نرخ یادگیری ملایم‌تر برای یادگیری ساختار پایدار
        max_depth=5,
        num_leaves=15,          # کاهش پیچیدگی درخت‌ها جهت انطباق با رفتار نوسانی بازار
        min_child_samples=15,
        subsample=0.7,           # نمونه‌گیری ردیفی بدون دستکاری توالی برای تعمیم‌دهی بهتر
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=1,
        verbose=-1
    )
    
    model.fit(
        X_train, 
        y_train,
        eval_set=[(X_test, y_test)]  # ارزیابی مستقیم روی داده‌های آینده واقعی
    )

    # --- ۵. ذخیره‌سازی ---
    safe_symbol_name = symbol.replace('/', '_')
    models_dir = os.path.join(BASE_DIR, "src", "models")
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, f"{safe_symbol_name}_model.pkl")
    
    joblib.dump(model, model_path)
    print(f"🎯 مدل {symbol} با موفقیت بدون نشت داده (Time-Series) ارتقا یافت.")

def train_all(mode="backtest"):
    for symbol in config.WATCHLIST:
        train_model_for_symbol(symbol, mode=mode)

if __name__ == "__main__":
    mode = "monthly" if "--monthly" in sys.argv else "backtest"
    train_all(mode=mode)

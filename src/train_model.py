# ---------------------------------------------------------
# FILE PATH: src/train_model.py (v8.2 - LightGBM + Full Data Logic)
# ---------------------------------------------------------
import sqlite3
import pandas as pd
import numpy as np
import os
import sys
import joblib
import logging
from lightgbm import LGBMClassifier
from sklearn.model_selection import train_test_split
import config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def get_data_from_db(db_path, symbol):
    """استخراج امن دیتا از دیتابیس"""
    if not os.path.exists(db_path): return pd.DataFrame()
    try:
        with sqlite3.connect(db_path) as conn:
            return pd.read_sql_query("SELECT * FROM signals WHERE symbol = ? AND status = 'CLOSED'", conn, params=(symbol,))
    except Exception as e:
        logging.error(f"خطای خواندن دیتابیس در {db_path}: {e}")
        return pd.DataFrame()

def train_model_for_symbol(symbol, mode="backtest"):
    # ۱. تجمیع هوشمند داده‌ها (منطق شما حفظ شد)
    if mode == "monthly":
        df_backtest = get_data_from_db(config.DB_PATH_BACKTEST, symbol)
        df_live = get_data_from_db(config.DB_PATH_LIVE, symbol)
        df = pd.concat([df_backtest, df_live], ignore_index=True)
    else:
        df = get_data_from_db(config.DB_PATH_BACKTEST, symbol)

    if df.empty: return

    # ۲. پیش‌پردازش دقیق (حفظ تمام فیچرهای شما)
    features = ['feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
                'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
                'feat_body_ratio', 'feat_high_volume_session']
    
    df = df.dropna(subset=features)
    df = df.drop_duplicates(subset=['timestamp']) # جلوگیری از تکرار

    if len(df) < 50: # حداقل ۵۰ معامله برای یادگیری معنادار
        return

    X = df[features]
    y = np.where(df['pnl_percent'] > 0, 1, 0)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # ۳. مدل LightGBM با تنظیمات بهینه (جایگزین RandomForest)
    model = LGBMClassifier(
        n_estimators=150,
        learning_rate=0.05,
        max_depth=6,
        num_leaves=31,
        min_child_samples=20,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=1,
        verbose=-1
    )
    
    model.fit(X_train, y_train)

    # ۴. ذخیره‌سازی با همان نام قبلی برای هماهنگی با brain.py
    safe_symbol_name = symbol.replace('/', '_')
    models_dir = os.path.join(BASE_DIR, "src", "models")
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, f"{safe_symbol_name}_model.pkl")
    
    joblib.dump(model, model_path)
    logging.info(f"🎯 مدل {symbol} با LightGBM ارتقا یافت ({len(df)} نمونه).")

def train_all(mode="backtest"):
    for symbol in config.WATCHLIST:
        train_model_for_symbol(symbol, mode=mode)

# ---------------------------------------------------------
# FILE PATH: src/train_model.py (v9.2 - Fixed for Local SQLite)
# ---------------------------------------------------------
import pandas as pd
import numpy as np
import os
import sys
import joblib
import logging
import sqlite3

try:
    from lightgbm import LGBMClassifier
except ImportError:
    print("CRITICAL: LightGBM is not installed.")
    sys.exit(1)

# تنظیم مسیر پایه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config

def get_data_from_db(symbol):
    """استخراج امن دیتا از دیتابیس بکتست محلی (SQLite)"""
    try:
        query = "SELECT * FROM signals WHERE symbol = ? AND status = 'CLOSED'"
        with sqlite3.connect(config.DB_PATH_BACKTEST) as conn:
            # تبدیل به دیتافریم
            df_res = pd.read_sql_query(query, conn, params=(symbol,))
            df_res.columns = [col.lower() for col in df_res.columns]
            return df_res
    except Exception as e:
        logging.error(f"❌ خطای دیتابیس محلی در استخراج {symbol}: {e}")
        return pd.DataFrame()

def train_model_for_symbol(symbol, mode="backtest"):
    # --- ۱. تجمیع داده‌ها (حفظ منطق اصلی) ---
    # در دیتابیس ابری، تمام داده‌ها در یک جدول هستند، اما برای حفظ منطقِ ماهانه شما:
    df = get_data_from_db(symbol)
    
    if df.empty:
        print(f"⚠️ دیتایی برای {symbol} یافت نشد.")
        return

    if 'pnl_percent' not in df.columns:
        print(f"⚠️ ستون pnl_percent در داده‌های {symbol} یافت نشد.")
        return

    # --- ۲. پیش‌پردازش کامل ---
    features = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
        'feat_body_ratio', 'feat_high_volume_session'
    ]
    
    missing_feats = [f for f in features if f not in df.columns]
    if missing_feats:
        print(f"⚠️ برخی ویژگی‌ها در دیتابیس یافت نشدند: {missing_feats}")
        return

    df['target_label'] = np.where(df['pnl_percent'] > 0, 1, 0)
    
    if df['target_label'].nunique() < 2:
        print(f"⚠️ مدل {symbol} قابل آموزش نیست (تنوع داده کم است).")
        return
    
    df = df.dropna(subset=features + ['target_label'])
    # استفاده از timestamp برای مرتب‌سازی (مطمئن شوید در دیتابیس ابری این ستون موجود است)
    df = df.sort_values(by='timestamp', ascending=True)
    df = df.drop_duplicates(subset=['timestamp'])
    
    if len(df) < 10: 
        print(f"⚠️ معاملات کافی برای ارتقای {symbol} موجود نیست ({len(df)}).")
        return

    X = df[features]
    y = df['target_label'].to_numpy()

    # --- ۳. تقسیم داده‌ها ---
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    if len(X_test) != len(y_test) or len(X_train) != len(y_train):
        print(f"⚠️ خطای داخلی عدم تطابق اندکس‌ها؛ انصراف از آموزش برای {symbol}")
        return

    # --- ۴. آموزش مدل ---
    model = LGBMClassifier(
        n_estimators=100, learning_rate=0.03, max_depth=5,
        num_leaves=15, min_child_samples=15, subsample=0.7,
        colsample_bytree=0.8, class_weight='balanced', 
        random_state=42, n_jobs=1, verbose=-1
    )
    
    if len(np.unique(y_test)) < 2:
        model.fit(X_train, y_train)
    else:
        model.fit(X_train, y_train, eval_set=[(X_test, y_test)])

    # --- ۵. ذخیره‌سازی ---
    safe_symbol_name = symbol.replace('/', '_')
    models_dir = os.path.join(BASE_DIR, "src", "models")
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, f"{safe_symbol_name}_model.pkl")
    
    joblib.dump(model, model_path)
    print(f"🎯 مدل {symbol} با موفقیت ارتقا یافت.")

def train_all(mode="backtest"):
    for symbol in config.WATCHLIST:
        train_model_for_symbol(symbol, mode=mode)

if __name__ == "__main__":
    mode = "monthly" if "--monthly" in sys.argv else "backtest"
    train_all(mode=mode)

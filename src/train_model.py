# ---------------------------------------------------------
# FILE PATH: src/train_model.py (v9.3 - Time-Decay Weighted & Cloud Aligned)
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

# تنظیم مسیر پایه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from src import database # 🟢 استفاده از ماژول دیتابیس جدید

def get_data_from_db(symbol):
    """استخراج امن دیتا از دیتابیس ابری (PostgreSQL/Supabase)"""
    try:
        query = "SELECT * FROM signals WHERE symbol = %s AND status = 'CLOSED'"
        with database.get_connection() as conn:
            df_res = pd.read_sql_query(query, conn, params=(symbol,))
            df_res.columns = [col.lower() for col in df_res.columns]
            return df_res
    except Exception as e:
        logging.error(f"❌ خطای دیتابیس ابری در استخراج {symbol}: {e}")
        return pd.DataFrame()

def train_model_for_symbol(symbol, mode="backtest"):
    # --- ۱. تجمیع داده‌ها ---
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
    df = df.sort_values(by='timestamp', ascending=True).reset_index(drop=True)
    df = df.drop_duplicates(subset=['timestamp'])
    
    if len(df) < 10: 
        print(f"⚠️ معاملات کافی برای ارتقای {symbol} موجود نیست ({len(df)}).")
        return

    X = df[features]
    y = df['target_label'].to_numpy()

    # --- ۳. سیستم ضد اورفیت: وزن‌دهی زمانی (Time-Decay) ---
    # داده‌های جدیدتر وزن بسیار بیشتری دارند تا مدل رفتار اخیر بازار را بهتر بشناسد
    decay_factor = 0.995
    sample_weights = np.power(decay_factor, np.arange(len(df)-1, -1, -1))

    # --- ۴. تنظیمات پویای آموزش بر اساس حالت اجرا ---
    # در حالت monthly مدل با تمام دیتای وزن‌دار آموزش می‌بیند تا کاملا آپدیت باشد
    if mode == "monthly":
        X_train, y_train = X, y
        train_weights = sample_weights
        eval_set = None
    else:
        # در حالت backtest همچنان اسپیلیت زمانی را برای ارزیابی حفظ می‌کنیم
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        train_weights = sample_weights[:split_idx]
        eval_set = [(X_test, y_test)]

    if mode != "monthly" and (len(X_test) != len(y_test) or len(X_train) != len(y_train)):
        print(f"⚠️ خطای داخلی عدم تطابق اندکس‌ها؛ انصراف از آموزش برای {symbol}")
        return

    # --- ۵. آموزش مدل (با تنظیمات کنترل‌شده برای جلوگیری از حفظ کردن چارت) ---
    model = LGBMClassifier(
        n_estimators=120, 
        learning_rate=0.03, 
        max_depth=4,              # کاهش عمق برای جلوگیری از اورفیت شدید
        num_leaves=10,            # برگ‌های کمتر، تعمیم‌پذیری بیشتر
        min_child_samples=20, 
        subsample=0.8,
        colsample_bytree=0.8, 
        class_weight='balanced', 
        random_state=42, 
        n_jobs=1, 
        verbose=-1
    )
    
    if eval_set and len(np.unique(y_test)) >= 2:
        model.fit(X_train, y_train, sample_weight=train_weights, eval_set=eval_set)
    else:
        model.fit(X_train, y_train, sample_weight=train_weights)

    # --- ۶. ذخیره‌سازی ابری/لوکال ---
    safe_symbol_name = symbol.replace('/', '_')
    models_dir = os.path.join(BASE_DIR, "src", "models")
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, f"{safe_symbol_name}_model.pkl")
    
    joblib.dump(model, model_path)
    print(f"🎯 مدل {symbol} با موفقیت ارتقا یافت (Mode: {mode}).")

def train_all(mode="backtest"):
    for symbol in config.WATCHLIST:
        train_model_for_symbol(symbol, mode=mode)

if __name__ == "__main__":
    mode = "monthly" if "--monthly" in sys.argv else "backtest"
    train_all(mode=mode)

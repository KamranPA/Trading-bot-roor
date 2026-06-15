# ---------------------------------------------------------
# FILE PATH: src/train_model.py (v8.6.1 - Fixed Data Imbalance Crash)
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
            df_res = pd.read_sql_query(
                "SELECT * FROM signals WHERE symbol = ? AND status = 'CLOSED'", 
                conn, params=(symbol,)
            )
            # تبدیل نام تمام ستون‌ها به حروف کوچک برای جلوگیری از KeyError
            df_res.columns = [col.lower() for col in df_res.columns]
            return df_res
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

    # بررسی وجود ستون کلیدی pnl_percent جهت جلوگیری از کرش پایپ‌لاین
    if 'pnl_percent' not in df.columns:
        print(f"⚠️ ستون pnl_percent در داده‌های {symbol} یافت نشد.")
        return

    # --- ۲. پیش‌پردازش کامل و پاک‌سازی داده‌ها (قبل از Split) ---
    features = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
        'feat_body_ratio', 'feat_high_volume_session'
    ]
    
    # بررسی وجود تمام فیچرها در دیتابیس
    missing_feats = [f for f in features if f not in df.columns]
    if missing_feats:
        print(f"⚠️ برخی ویژگی‌ها در دیتابیس یافت نشدند: {missing_feats}")
        return

    # ساخت ستون هدف داخل خود دیتافریم
    df['target_label'] = np.where(df['pnl_percent'] > 0, 1, 0)
    
    # ⚠️ بررسی تعادل دیتا: آیا حداقل یک سود و یک ضرر داریم؟
    if df['target_label'].nunique() < 2:
        print(f"⚠️ مدل {symbol} قابل آموزش نیست (داده‌های شما فقط شامل سود یا فقط شامل ضرر است).")
        return
    
    # ⚠️ اصلاح ترتیب (مهم): ابتدا فیلترها و حذف تکراری‌ها روی کل دیتافریم اعمال می‌شود
    df = df.dropna(subset=features + ['target_label'])
    df = df.sort_values(by='timestamp', ascending=True)
    df = df.drop_duplicates(subset=['timestamp'])
    
    # بررسی حداقل تعداد داده‌های تصفیه شده
    if len(df) < 10: 
        print(f"⚠️ معاملات کافی برای ارتقای {symbol} پس از فیلتر موجود نیست ({len(df)}).")
        return

    # استخراج نهایی ماتریس‌ها به صورت کاملاً تصفیه شده و هم‌تراز
    X = df[features]
    y = df['target_label'].to_numpy()

    # --- ۳. تقسیم داده‌ها بدون Shuffle بر اساس طول نهایی ماتریس تصفیه شده ---
    split_idx = int(len(X) * 0.8)
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    # اطمینان نهایی چشمی برای ستون‌ها و ردیف‌ها
    if len(X_test) != len(y_test) or len(X_train) != len(y_train):
        print(f"⚠️ خطای داخلی عدم تطابق اندکس‌ها؛ انصراف از آموزش برای {symbol}")
        return

    # --- ۴. آموزش مدل LightGBM ---
    # اضافه شدن class_weight='balanced' برای رفع خطای Imbalance و عدم تعادل کلاس‌ها
    model = LGBMClassifier(
        n_estimators=100,       
        learning_rate=0.03,      
        max_depth=5,
        num_leaves=15,          
        min_child_samples=15,
        subsample=0.7,           
        colsample_bytree=0.8,
        class_weight='balanced', 
        random_state=42,
        n_jobs=1,
        verbose=-1
    )
    
    # ارزیابی دقیق بدون خطای طول ماتریس
    model.fit(
        X_train, 
        y_train,
        eval_set=[(X_test, y_test)]  
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

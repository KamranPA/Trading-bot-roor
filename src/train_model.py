# ---------------------------------------------------------
# FILE PATH: src/train_model.py (v8.1 - Continuous Monthly Learning)
# ---------------------------------------------------------
import sqlite3
import pandas as pd
import numpy as np
import os
import sys
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config

def get_data_from_db(db_path, symbol):
    """استخراج امن دیتا از دیتابیس مشخص شده"""
    if not os.path.exists(db_path):
        return pd.DataFrame()
    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(
                "SELECT * FROM signals WHERE symbol = ? AND status = 'CLOSED'", 
                conn, params=(symbol,)
            )
        return df
    except Exception as e:
        print(f"❌ خطای خواندن دیتابیس در {db_path}: {e}")
        return pd.DataFrame()

def train_model_for_symbol(symbol, mode="backtest"):
    """
    آموزش مدل هوش مصنوعی اختصاصی برای یک ارز خاص
    mode="backtest": فقط دیتای شبیه‌سازی (برای شروع کار)
    mode="monthly": ترکیب دیتای بکتست + لایو (برای یادگیری مستمر ماهانه)
    """
    df = pd.DataFrame()
    
    # --- ۱. تجمیع هوشمند داده‌ها ---
    if mode == "monthly":
        print(f"🔄 [Monthly Retrain] در حال استخراج دیتای ترکیبی (لایو + بکتست) برای {symbol}...")
        df_backtest = get_data_from_db(config.DB_PATH_BACKTEST, symbol)
        df_live = get_data_from_db(config.DB_PATH_LIVE, symbol)
        
        # ترکیب دیتاها (پویایی: دیتای لایو در آینده می‌تواند وزن بیشتری بگیرد)
        df = pd.concat([df_backtest, df_live], ignore_index=True)
    else:
        df = get_data_from_db(config.DB_PATH_BACKTEST, symbol)

    if df.empty:
        return

    # --- ۲. پیش‌پردازش داده‌ها ---
    features = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
        'feat_body_ratio', 'feat_high_volume_session'
    ]
    
    df = df.dropna(subset=features)
    
    if len(df) < 10:
        print(f"⚠️ دیتای کافی برای ارتقای {symbol} نیست ({len(df)} معامله).")
        return

    # حذف داده‌های تکراری احتمالی بر اساس زمان
    df = df.drop_duplicates(subset=['timestamp'])

    X = df[features]
    y = np.where(df['pnl_percent'] > 0, 1, 0)

    # --- ۳. آموزش مدل پویا ---
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(
        n_estimators=100,      # افزایش تعداد درخت‌ها برای یادگیری عمیق‌تر از خطاهای لایو
        max_depth=7,           # کمی عمیق‌تر برای درک الگوهای پیچیده‌تر ماهانه
        class_weight='balanced',
        random_state=42
    )
    
    model.fit(X_train, y_train)

    # --- ۴. ذخیره‌سازی ایمن ---
    safe_symbol_name = symbol.replace('/', '_')
    model_path = os.path.join(BASE_DIR, "src", "models", f"{safe_symbol_name}_model.pkl")
    
    joblib.dump(model, model_path)
    print(f"🎯 [AI Trained] مدل {symbol} با موفقیت ارتقا یافت -> {len(df)} معامله (حالت: {mode}).")

def train_all(mode="backtest"):
    print(f"🤖 [AI Multi-Model Pipeline] شروع آموزش زنجیره‌ای در حالت: {mode}")
    os.makedirs(os.path.join(BASE_DIR, "src", "models"), exist_ok=True)
    for symbol in config.WATCHLIST:
        train_model_for_symbol(symbol, mode=mode)

if __name__ == "__main__":
    # اگر اسکریپت با آرگومان --monthly اجرا شد، به حالت یادگیری پیوسته می‌رود
    if len(sys.argv) > 1 and sys.argv[1] == "--monthly":
        train_all(mode="monthly")
    else:
        train_all(mode="backtest")

# ---------------------------------------------------------
# FILE PATH: src/train_model.py (v8.1 - Continuous Monthly Learning)
# ---------------------------------------------------------
import sys
import os
# حل باگ عدم شناسایی ماژول src در سرورهای لینوکسی لایو گیت‌هاب
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
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
    """آموزش مدل هوش مصنوعی اختصاصی برای هر ارز خاص بر اساس ویژگی‌های ثبت شده"""
    df = pd.DataFrame()
    
    if mode == "monthly":
        df_backtest = get_data_from_db(config.DB_PATH_BACKTEST, symbol)
        df_live = get_data_from_db(config.DB_PATH_LIVE, symbol)
        df = pd.concat([df_backtest, df_live], ignore_index=True)
    else:
        df = get_data_from_db(config.DB_PATH_BACKTEST, symbol)

    if df.empty:
        return

    features = [
        'feat_adx', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
        'feat_body_ratio'
    ]
    
    df = df.dropna(subset=features)
    
    if len(df) < 10:
        print(f"⚠️ تعداد سیگنال‌های {symbol} به حد نصاب ۱۰ عدد نرسیده است ({len(df)} معامله).")
        return

    df = df.drop_duplicates(subset=['timestamp'])

    X = df[features]
    y = np.where(df['pnl_percent'] > 0, 1, 0)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=7,
        class_weight='balanced',
        random_state=42
    )
    
    model.fit(X_train, y_train)

    safe_symbol_name = symbol.replace('/', '_')
    model_dir = os.path.join(config.BASE_DIR, "src", "models")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, f"{safe_symbol_name}_model.pkl")
    
    joblib.dump(model, model_path)
    print(f"🎯 [AI Model Trained] مدل اختصاصی {symbol} با موفقیت در مسیر ذخیره شد.")

def train_all(mode="backtest"):
    print(f"🤖 [AI Pipeline] شروع فرآیند آموزش شبکه‌ای مدل‌ها در حالت: {mode}")
    for symbol in config.WATCHLIST:
        train_model_for_symbol(symbol, mode=mode)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--monthly":
        train_all(mode="monthly")
    else:
        train_all(mode="backtest")

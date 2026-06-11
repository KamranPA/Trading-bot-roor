# ---------------------------------------------------------
# FILE PATH: src/train_model.py (v8.0 - Multi-Model Training)
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

def train_model_for_symbol(symbol, mode="backtest"):
    """آموزش مدل هوش مصنوعی اختصاصی برای یک ارز خاص"""
    db_path = config.DB_PATH_BACKTEST if mode == "backtest" else config.DB_PATH_LIVE
    
    if not os.path.exists(db_path):
        return

    try:
        conn = sqlite3.connect(db_path)
        # فقط دیتای همین ارز را بخوان
        df = pd.read_sql_query("SELECT * FROM signals WHERE symbol = ? AND status = 'CLOSED'", conn, params=(symbol,))
        conn.close()
    except Exception as e:
        print(f"❌ خطای دیتابیس برای {symbol}: {e}")
        return

    features = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
        'feat_body_ratio', 'feat_high_volume_session'
    ]
    
    df = df.dropna(subset=features)
    
    # حد نصاب برای هر ارز را ۳۰ معامله قرار می‌دهیم تا سریع‌تر مدل‌ها شکل بگیرند
    if len(df) < 30:
        print(f"⚠️ دیتای کافی برای {symbol} نیست ({len(df)} معامله). نیاز به ترتریب معاملات بیشتر.")
        return

    X = df[features]
    y = np.where(df['pnl_percent'] > 0, 1, 0)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(
        n_estimators=80, 
        max_depth=6, 
        class_weight='balanced',
        random_state=42
    )
    
    model.fit(X_train, y_train)

    # نام‌گذاری فایل مدل به صورت اختصاصی بر اساس نام ارز
    safe_symbol_name = symbol.replace('/', '_')
    model_path = os.path.join(BASE_DIR, "src", "models", f"{safe_symbol_name}_model.pkl")
    
    joblib.dump(model, model_path)
    print(f"🎯 [AI Train] مدل اختصاصی ارز {symbol} با موفقیت آپدیت شد -> {len(df)} معامله.")

def train_all():
    print("🤖 [AI Multi-Model Pipeline] شروع آموزش زنجیره‌ای مدل‌های انحصاری...")
    os.makedirs(os.path.join(BASE_DIR, "src", "models"), exist_ok=True)
    for symbol in config.WATCHLIST:
        train_model_for_symbol(symbol, mode="backtest")

if __name__ == "__main__":
    train_all()

# ---------------------------------------------------------
# FILE NAME: train_model.py
# FILE PATH: /src/train_model.py
# ---------------------------------------------------------
import sqlite3
import pandas as pd
import numpy as np
import os
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

def train_filter_model():
    """🧠 آموزش مجدد مدل هوش مصنوعی بدون استفاده از ویژگی‌های حجمی"""
    db_path = "data/trading_bot.db"
    model_dir = "src/models"
    model_path = os.path.join(model_dir, "trading_filter_model.pkl")
    
    os.makedirs(model_dir, exist_ok=True)
    
    if not os.path.exists(db_path):
        print(f"❌ دیتابیس یافت نشد: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query("SELECT * FROM signals WHERE status = 'CLOSED'", conn)
        conn.close()
    except Exception as e:
        print(f"❌ خطای پایگاه داده: {e}")
        return

    # تعریف ویژگی‌های سیستم بدون فیلترهای حجم
    features = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 'feat_body_ratio'
    ]
    
    df = df.dropna(subset=features)
    
    if len(df) < 50:
        print(f"⚠️ دیتای کافی موجود نیست ({len(df)} معامله). مدل برای آپدیت شدن به ۵0 معامله بسته شده نیاز دارد.")
        return

    X = df[features]
    y = np.where(df['pnl_percent'] > 0, 1, 0)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(
        n_estimators=100, 
        max_depth=7, 
        min_samples_split=5,
        class_weight='balanced',
        random_state=42
    )
    
    model.fit(X_train, y_train)

    print("📊 گزارش نهایی دقت مدل بدون فیلتر حجم:")
    predictions = model.predict(X_test)
    print(classification_report(y_test, predictions))

    joblib.dump(model, model_path)
    print(f"✅ مدل هوشمند با موفقیت فاقد فیلتر حجم آپدیت شد: {model_path}")

if __name__ == "__main__":
    train_filter_model()

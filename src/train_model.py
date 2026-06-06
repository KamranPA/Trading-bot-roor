# src/train_model.py
# نسخه v7.3 - آموزش هوش مصنوعی با تمرکز بر داده‌های واقعی معاملات بسته شده (CLOSED)

import os
import sqlite3
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from src import database  # وارد کردن ماژول دیتابیس برای دسترسی به مسیرها

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "src", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "trading_filter_model.pkl")

def train_ai_model():
    if not os.path.exists(database.DB_NAME):
        print("ℹ️ دیتابیس هنوز تشکیل نشده است. تعلیق آموزش.")
        return

    conn = sqlite3.connect(database.DB_NAME)
    
    # 🟢 کوئری روی هر ۹ فاکتور اصلی دیتابیس - فقط معاملات CLOSED برای یادگیری دقیق
    query = """
        SELECT 
            feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line,
            feat_ema_deviation, feat_rsi_momentum, feat_body_ratio, feat_high_volume_session,
            pnl_percent 
        FROM signals 
        WHERE status = 'CLOSED'
    """
    
    try:
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"⚠️ خطای خواندن دیتابیس برای آموزش هوش مصنوعی: {e}")
        conn.close()
        return
    finally:
        conn.close()

    # شرط ایمن: بررسی وجود حداقل ۵۰ معامله بسته شده برای جلوگیری از بیش‌برازش (Overfitting)
    if len(df) < 50:
        print(f"ℹ️ حجم تاریخچه معاملات بسته شده کم است ({len(df)}/50). تعلیق کالیبراسیون هوش مصنوعی.")
        return

    # تعریف ستون هدف (اگر سود معامله بالای صفر باشد = ۱، در غیر این صورت = ۰)
    df['target'] = (df['pnl_percent'] > 0).astype(int)
    
    # ۹ فاکتور ورودی برای یادگیری ماشین
    features = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line',
        'feat_ema_deviation', 'feat_rsi_momentum', 'feat_body_ratio', 'feat_high_volume_session'
    ]
    
    X = df[features]
    y = df['target']

    # پیکربندی بهینه مدل جنگل تصادفی با وزن‌دهی متعادل به کلاس‌ها برای جلوگیری از بایاس
    model = RandomForestClassifier(
        n_estimators=100, 
        max_depth=5, 
        class_weight='balanced', 
        random_state=42
    )
    model.fit(X, y)

    # ذخیره‌سازی مدل در پوشه models
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"🔥 هوش مصنوعی ۹ بعدی با موفقیت روی {len(df)} معامله آموزش و در {MODEL_PATH} ذخیره شد.")

if __name__ == "__main__":
    train_ai_model()

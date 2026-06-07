# ---------------------------------------------------------
# FILE PATH: /src/train_model.py
# ---------------------------------------------------------

import os
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "data", "trading_bot.db")
MODEL_DIR = os.path.join(BASE_DIR, "src", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "trading_filter_model.pkl")

def train_ai_model():
    if not os.path.exists(DB_NAME):
        return

    conn = sqlite3.connect(DB_NAME)
    # استخراج تمام فاکتورهای موجود (سیستم داینامیک برای ۱۰ فاکتور و بیشتر)
    query = "SELECT * FROM signals WHERE status = 'CLOSED'"
    
    try:
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"❌ خطا در خواندن دیتابیس: {e}")
        conn.close()
        return
    finally:
        conn.close()

    if len(df) < 50:
        print(f"ℹ️ حجم دیتا کم است ({len(df)}/50). آموزش معلق شد.")
        return

    # تعریف ستون هدف
    df['target'] = (df['pnl_percent'] > 0).astype(int)
    
    # شناسایی خودکار فاکتورها (تمام ستون‌هایی که با feat_ شروع می‌شوند)
    features = [col for col in df.columns if col.startswith('feat_')]
    
    X = df[features]
    y = df['target']

    # آموزش مدل با ۱۰+ فاکتور
    model = RandomForestClassifier(n_estimators=200, max_depth=7, class_weight='balanced', random_state=42)
    model.fit(X, y)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"🔥 مدل ۱۰+ بعدی با موفقیت آموزش دید. فاکتورهای استفاده شده: {len(features)}")

if __name__ == "__main__":
    train_ai_model()

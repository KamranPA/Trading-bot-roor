# src/train_model.py
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
    # 🟢 کوئری روی ۵ فاکتور اصلی دیتابیس قفل شد
    query = """
        SELECT 
            feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line,
            pnl_percent 
        FROM signals 
        WHERE status = 'CLOSED'
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if len(df) < 50:
        print(f"ℹ️ حجم تاریخچه معاملات کم است ({len(df)}/50). تعلیق مدل.")
        return

    df['target'] = (df['pnl_percent'] > 0).astype(int)
    features = ['feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line']
    
    X = df[features]
    y = df['target']

    model = RandomForestClassifier(n_estimators=100, max_depth=5, class_weight='balanced', random_state=42)
    model.fit(X, y)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print("🔥 مدل کالیبره و ذخیره شد.")

if __name__ == "__main__":
    train_ai_model()

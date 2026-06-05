# src/train_model.py
# ماژول آموزش مدل یادگیری ماشین الگوریتم Random Forest بر اساس پوزیشن‌های بسته شده

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
    """🧠 آموزش موتور هوش مصنوعی بر اساس تاریخچه معاملات بسته‌شده گذشته"""
    if not os.path.exists(DB_NAME):
        print("⚠️ پایگاه داده پیدا نشد.")
        return

    conn = sqlite3.connect(DB_NAME)
    query = """
        SELECT 
            feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line,
            feat_ema_deviation, feat_rsi_momentum, feat_body_ratio, feat_high_volume_session,
            pnl_percent 
        FROM signals 
        WHERE status = 'CLOSED'
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    # حداقل حد آستانه ۵۰ معامله بسته شده جهت جلوگیری از Overfitting
    if len(df) < 50:
        print(f"ℹ️ حجم معاملات کم است ({len(df)}/50 معامله). کالیبراسیون هوش مصنوعی تعلیق ماند.")
        return

    df['target'] = (df['pnl_percent'] > 0).astype(int)

    features = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line',
        'feat_ema_deviation', 'feat_rsi_momentum', 'feat_body_ratio', 'feat_high_volume_session'
    ]
    
    X = df[features]
    y = df['target']

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=5,
        class_weight='balanced',
        random_state=42
    )
    model.fit(X, y)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"🔥 مدل جدید هوش مصنوعی با موفقیت آموزش دیده و ذخیره شد.")

if __name__ == "__main__":
    train_ai_model()

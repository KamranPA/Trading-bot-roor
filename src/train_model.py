# src/train_model.py
# نسخه اصلاح‌شده ۳۶۰ درجه خالص (v6.3) - کالیبره شده با ۵ فاکتور اصلی دیتابیس

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
    """🧠 آموزش موتور هوش مصنوعی بر اساس ۵ فاکتور اصیل دیتابیس ۳۶۰ درجه"""
    if not os.path.exists(DB_NAME):
        print("⚠️ پایگاه داده جهت استخراج دیتای آموزشی هوش مصنوعی پیدا نشد.")
        return

    conn = sqlite3.connect(DB_NAME)
    # 🟢 اصلاح کلیدی: حذف ستون‌های اضافی که باعث ارور no such column و کرش سیستم می‌شدند
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
        print(f"ℹ️ حجم تاریخچه معاملات کم است ({len(df)}/50 معامله بسته‌شده). کالیبراسیون هوش مصنوعی تعلیق ماند.")
        return

    df['target'] = (df['pnl_percent'] > 0).astype(int)

    # 🟢 تنظیم دقیق روی ۵ ویژگی اصلی شما
    features = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line'
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
    print(f"🔥 [هوش مصنوعی با موفقیت کالیبره شد]: مدل جدید با ۵ فاکتور اصیل ذخیره گردید.")

if __name__ == "__main__":
    train_ai_model()

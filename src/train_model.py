# src/train_model.py
# موتور هوش مصنوعی ربات (نسخه v5.6 - آموزش مدل یادگیری ماشین ۵ فاکتوره با دید ۳۶۰ درجه)

import os
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trading_bot.db")
MODEL_DIR = os.path.join(BASE_DIR, "src", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "trading_filter_model.pkl")

if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR)

def load_data_from_db():
    if not os.path.exists(DB_PATH):
        print("⚠️ دیتابیس یافت نشد!")
        return None
        
    conn = sqlite3.connect(DB_PATH)
    # استخراج دیتای هر ۵ متد تکنیکال
    query = """
        SELECT feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line, pnl_percent 
        FROM signals 
        WHERE status = 'CLOSED' AND (feat_adx > 0 OR feat_vol_ratio > 0)
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def train_ai_model():
    print("🧠 فرآیند کالبدشکافی داده‌ها و آموزش مدل هوش مصنوعی ۳۶۰ درجه آغاز شد...")
    df = load_data_from_db()
    
    if df is None or len(df) < 10:
        print(f"ℹ️ تعداد معاملات بسته شده برای آموزش کافی نیست (فعلاً {len(df) if df is not None else 0} معامله).")
        return False

    # تعریف ورودی‌های پنج‌گانه سنسورها
    X = df[['feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line']]
    y = df['pnl_percent'].apply(lambda x: 1 if x > 0 else 0)
    
    print(f"📊 حجم دیتای در دسترس برای یادگیری: {len(df)} معامله.")

    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X, y)
    
    joblib.dump(model, MODEL_PATH)
    print(f"💾 فایل مغز الکترونیک هوش مصنوعی ۵ فاکتوره با موفقیت ذخیره شد: {MODEL_PATH}")
    return True

if __name__ == "__main__":
    train_ai_model()

# File Path: /src/train_model.py
import sqlite3
import os
import joblib  # اصلاح شد
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

DB_NAME = "data/trading_bot.db"
MODEL_DIR = "ml_models"
MODEL_PATH = os.path.join(MODEL_DIR, "rf_trading_model.pkl")

def train_filter_model():
    """اصلاح شد: نام تابع برای هماهنگی با اکشن ماهانه گیت‌هاب تغییر یافت"""
    if not os.path.exists(DB_NAME):
        print("❌ دیتابیس یافت نشد. فرآیند آموزش لغو شد.")
        return

    try:
        with sqlite3.connect(DB_NAME) as conn:
            query = """
                SELECT atr, adx, rsi, ema_diff, pnl_percent 
                FROM signals 
                WHERE status = 'CLOSED'
            """
            df = pd.read_sql_query(query, conn)

        if len(df) < 50:
            print(f"ℹ️ داده‌ها کافی نیست ({len(df)}/50). آموزش انجام نمی‌شود.")
            return

        df['target'] = (df['pnl_percent'] > 0).astype(int)
        
        feature_cols = ['atr', 'adx', 'rsi', 'ema_diff']
        X = df[feature_cols]
        y = df['target']
        
        print(f"🔄 آموزش مدل هوش مصنوعی با {len(df)} معامله واقعی...")
        
        model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        model.fit(X, y)
        
        if not os.path.exists(MODEL_DIR):
            os.makedirs(MODEL_DIR)
            
        with open(MODEL_PATH, 'wb') as f:
            joblib.dump(model, f)  # اصلاح شد
            
        print("🧠 مدل هوش مصنوعی با موفقیت بروزرسانی شد.")

    except Exception as e:
        print(f"❌ خطا در فرآیند آموزش مدل: {e}")

if __name__ == "__main__":
    train_filter_model()

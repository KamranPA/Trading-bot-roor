# ---------------------------------------------------------
# FILE NAME: train_model.py
# FILE PATH: /src/train_model.py
# ---------------------------------------------------------
import sqlite3
import os
import jobpath
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

DB_NAME = "trading_bot.db"
MODEL_DIR = "ml_models"
MODEL_PATH = os.path.join(MODEL_DIR, "rf_trading_model.pkl")

def train_ai_model():
    """آموزش مجدد مدل یادگیری ماشین بر اساس تاریخچه معاملات واقعی ربات"""
    if not os.path.exists(DB_NAME):
        print("❌ دیتابیس یافت نشد. آموزش لغو شد.")
        return

    try:
        with sqlite3.connect(DB_NAME) as conn:
            # خواندن کلیدی‌ترین ویژگی‌ها به همراه سود/زیان پوزیشن‌های بسته شده
            query = """
                SELECT atr, adx, rsi, ema_diff, pnl_percent 
                FROM signals 
                WHERE status = 'CLOSED'
            """
            df = pd.read_sql_query(query, conn)

        if len(df) < 50:
            print(f"ℹ️ تعداد داده‌های بسته شده کافی نیست ({len(df)}/50). برای پیشگیری از بیش‌برازش آموزش انجام نمی‌شود.")
            return

        # برچسب‌گذاری: اگر سود مثبت باشد ۱ (موفق) و در غیر این صورت ۰ (ناموفق)
        df['target'] = (df['pnl_percent'] > 0).astype(int)
        
        feature_cols = ['atr', 'adx', 'rsi', 'ema_diff']
        X = df[feature_cols]
        y = df['target']
        
        print(f"🔄 در حال آموزش مدل هوش مصنوعی با {len(df)} نمونه داده واقعی...")
        
        model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        model.fit(X, y)
        
        if not os.path.exists(MODEL_DIR):
            os.makedirs(MODEL_DIR)
            
        with open(MODEL_PATH, 'wb') as f:
            jobpath.dump(model, f)
            
        print("🧠 مدل هوش مصنوعی با موفقیت آپدیت و ذخیره شد.")

    except Exception as e:
        print(f"❌ خطا در فرآیند آموزش مدل: {e}")

if __name__ == "__main__":
    train_ai_model()

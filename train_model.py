# src/train_model.py
# نسخه نهایی v7.0 - آموزش موتور یادگیری ماشین بر اساس ۹ فاکتور پیشرفته هوش مصنوعی ۳۶۰ درجه

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
        print("ℹ️ دیتابیس هنوز تشکیل نشده است. تعلیق آموزش.")
        return

    conn = sqlite3.connect(DB_NAME)
    # 🟢 کوئری روی هر ۹ فاکتور اصلی دیتابیس قفل شد
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
        print(f"⚠️ خطای خواندن ستون‌های جدید از دیتابیس (احتمالاً هنوز معامله جدیدی ثبت نشده است): {e}")
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

    # پیکربندی بهینه مدل جنگل تصادفی با وزن‌دهی متعادل به کلاس‌ها
    model = RandomForestClassifier(n_estimators=100, max_depth=5, class_weight='balanced', random_state=42)
    model.fit(X, y)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print("🔥 هوش مصنوعی ۹ بعدی با موفقیت کالیبره، آموزش و ذخیره شد.")

if __name__ == "__main__":
    train_ai_model()

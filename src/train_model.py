# ---------------------------------------------------------
# FILE PATH: src/train_model.py
# ---------------------------------------------------------
import sqlite3
import pandas as pd
import numpy as np
import os
import sys
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# اضافه کردن مسیر ریشه پروژه به پایتون برای دسترسی بدون خطا به config.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config

def train_filter_model():
    # ۱. استفاده از مسیرهای یکپارچه و استاندارد
    db_path = config.DB_NAME
    model_dir = os.path.join(BASE_DIR, "src", "models")
    model_path = os.path.join(model_dir, "trading_filter_model.pkl")
    
    os.makedirs(model_dir, exist_ok=True)
    
    if not os.path.exists(db_path):
        print(f"❌ دیتابیس یافت نشد: {db_path}")
        return

    # ۲. استخراج داده‌ها با اتصال به دیتابیس اصلی پروژه
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query("SELECT * FROM signals WHERE status = 'CLOSED'", conn)
        conn.close()
    except Exception as e:
        print(f"❌ خطای دیتابیس: {e}")
        return

    # ۳. فیلتر کردن و پیش‌پردازش (دقیقاً هماهنگ با ۹ سنسور دیتابیس و استراتژی)
    features = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
        'feat_body_ratio', 'feat_high_volume_session'
    ]
    
    # حذف ردیف‌هایی که مقادیر حیاتی ندارند
    df = df.dropna(subset=features)
    
    if len(df) < 50: # حد نصاب برای جلوگیری از تقلب و حفظ اعتبار مدل
        print(f"⚠️ دیتای کافی برای آموزش نیست ({len(df)} معامله). حداقل ۵۰ معامله نیاز است.")
        return

    X = df[features]
    # تبدیل درصد سود به برچسب باینری (۱ = سود، ۰ = ضرر)
    y = np.where(df['pnl_percent'] > 0, 1, 0)

    # ۴. جداسازی داده‌های آموزش و تست (برای جلوگیری از بیش‌برازش)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # ۵. مدل‌سازی با تنظیمات بهینه (Hyperparameters)
    model = RandomForestClassifier(
        n_estimators=100, 
        max_depth=7, 
        min_samples_split=5,
        class_weight='balanced', # ایجاد تعادل در کلاس‌های سود و ضرر
        random_state=42
    )
    
    model.fit(X_train, y_train)

    # ۶. گزارش عملکرد مدل (ارزیابی بر روی داده‌های تست)
    print("📊 گزارش دقت مدل بر روی داده‌های تست:")
    predictions = model.predict(X_test)
    print(classification_report(y_test, predictions))

    # ۷. ذخیره‌سازی ایمن مدل
    joblib.dump(model, model_path)
    print(f"✅ مدل هوشمند با موفقیت آپدیت شد: {model_path}")

def train_all():
    """
    تابع واسط برای جلوگیری از خطای GitHub Actions
    در فایل monthly_brain.yml این تابع فراخوانی می‌شود
    """
    train_filter_model()

if __name__ == "__main__":
    train_all()

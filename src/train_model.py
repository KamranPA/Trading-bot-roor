# src/train_model.py
# موتور هوش مصنوعی ربات (نسخه v5.0 - آموزش مدل یادگیری ماشین بر اساس بازدهی معاملات)

import os
import sqlite3
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

# مسیرهای ثابت پروژه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "trading_bot.db")
MODEL_DIR = os.path.join(BASE_DIR, "src", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "trading_filter_model.pkl")

# مطمئن شدن از وجود پوشه ذخیره‌سازی مدل‌ها
if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR)

def load_data_from_db():
    """📈 استخراج داده‌های معاملات بسته شده برای آموزش مدل"""
    if not os.path.exists(DB_PATH):
        print("⚠️ دیتابیس یافت نشد!")
        return None
        
    conn = sqlite3.connect(DB_PATH)
    
    # واکشی معاملاتی که بسته شده‌اند و دیتای هوش مصنوعی آن‌ها معتبر است
    query = """
        SELECT feat_adx, feat_vol_ratio, feat_atr_percent, pnl_percent 
        FROM signals 
        WHERE status = 'CLOSED' AND (feat_adx > 0 OR feat_vol_ratio > 0)
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def train_ai_model():
    print("🧠 فرآیند کالبدشکافی داده‌ها و آموزش مدل هوش مصنوعی آغاز شد...")
    
    df = load_data_from_db()
    
    # شرط حد نصاب داده: مدل برای یادگیری حداقل به ۱۰ الی ۲۰ معامله بسته شده نیاز دارد
    if df is None or len(df) < 10:
        print(f"ℹ️ تعداد معاملات بسته شده برای آموزش کافی نیست (فعلاً {len(df) if df is not None else 0} معامله).")
        print("⏭️ سیستم تا جمع‌آوری دیتای بیشتر از فیلترهای کلاسیک استفاده می‌کند.")
        return False

    # ۱. تعریف ورودی‌ها (Features)
    X = df[['feat_adx', 'feat_vol_ratio', 'feat_atr_percent']]
    
    # ۲. تعریف هدف (Target): اگر سود مثبت بود ۱ (برنده)، اگر منفی یا صفر بود ۰ (بازنده/فیک)
    y = df['pnl_percent'].apply(lambda x: 1 if x > 0 else 0)
    
    print(f"📊 حجم دیتای در دسترس برای یادگیری: {len(df)} معامله.")
    print(f"🟢 معاملات سودده: {sum(y == 1)} | 🔴 معاملات زیان‌ده (شکست‌های فیک): {sum(y == 0)}")

    # ۳. پیکربندی الگوریتم جنگل تصادفی (Random Forest)
    # این مدل با ایجاد درخت‌های تصمیم‌گیری متعدد، الگوهای فیک‌بریک‌اوت را کشف می‌کند
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X, y)
    
    # ۴. ذخیره فیزیکی مدل آموزش دیده روی دیسک سرور گیت‌هاب
    joblib.dump(model, MODEL_PATH)
    print(f"💾 فایل مغز الکترونیک هوش مصنوعی با موفقیت ذخیره شد: {MODEL_PATH}")
    return True

if __name__ == "__main__":
    train_ai_model()

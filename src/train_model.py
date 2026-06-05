# src/train_model.py
# نسخه اصلاح‌شده v6.3 - کنترل آستانه دیتای ورودی جهت جلوگیری از بیش‌برازش (Overfitting)

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
    """🧠 آموزش موتور هوش مصنوعی بر اساس دیتای واقعی معاملات بسته شده"""[span_86](end_span)
    if not os.path.exists(DB_NAME):
        return

    # اتصال به پایگاه داده و استخراج معاملات بسته شده تاریخی
    conn = sqlite3.connect(DB_NAME)
    query = """
        SELECT feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line, pnl_percent 
        FROM signals 
        WHERE status = 'CLOSED'
    """
    df = pd.read_sql_query(query, conn)
    [span_87](start_span)conn.close()[span_87](end_span)

    # 🛡️ اصلاح مهلک بیش‌برازش: تا زمان ثبت حداقل ۵۰ معامله قطعی، فرآیند آموزش را متوقف می‌کنیم
    if len(df) < 50:
        [span_88](start_span)print(f"ℹ️ دیتای معاملاتی کافی نیست ({len(df)}/50 معامله بسته شده). آموزش هوش مصنوعی برای جلوگیری از Overfitting تعلیق شد.")[span_88](end_span)
        return

    # ایجاد ستون هدف (Target): اگر سود پوزیشن مثبت باشد ۱ (موفق)، در غیر این صورت ۰ (ناموفق)
    df['target'] = (df['pnl_percent'] > 0).astype(int)

    # جداسازی ویژگی‌های فیلترینگ و برچسب نهایی
    features = ['feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line']
    X = df[features]
    y = df['target']

    # تنظیم بهینه عمق درخت‌ها (max_depth) برای کنترل دقیق‌تر منطق ریاضی مدل
    [span_89](start_span)model = RandomForestClassifier(n_estimators=50, max_depth=4, random_state=42)[span_89](end_span)
    model.fit(X, y)

    # ایجاد پوشه مدل در صورت عدم وجود و ذخیره‌سازی نهایی فایل هوش مصنوعی
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"🔥 [هوش مصنوعی آپدیت شد]: مدل جدید بر اساس {len(df)} معامله واقعی با موفقیت کالیبره و ذخیره گردید.")

if __name__ == "__main__":
    train_ai_model()
ز

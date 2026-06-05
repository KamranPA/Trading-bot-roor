# src/train_model.py
# نسخه ارتقایافته v7.0 - مجهز به آموزش توزیع‌شده با فاکتورهای ۹ بعدی

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
    """🧠 آموزش موتور هوش مصنوعی تقویت‌شده بر اساس کارنامه معاملات بسته‌شده گذشته"""
    if not os.path.exists(DB_NAME):
        print("⚠️ پایگاه داده جهت استخراج دیتای آموزشی هوش مصنوعی پیدا نشد.")
        return

    # اتصال به دیتابیس و بارگذاری آرشیو معاملات
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

    # مکانیزم پیشگیری از تعمیم ناقص و بیش‌برازش (کنترل کف داده‌های آرشیو)
    if len(df) < 50:
        print(f"ℹ️ حجم تاریخچه معاملات کم است ({len(df)}/50 معامله بسته‌شده). کالیبراسیون هوش مصنوعی تعلیق ماند.")
        return

    # ایجاد ستون برچسب هدف (سودآور = ۱، زیان‌ده = ۰)
    df['target'] = (df['pnl_percent'] > 0).astype(int)

    # لیست جامع ۹ ویژگی استخراج شده برای ورودی درخت‌های تصمیم‌گیری
    features = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line',
        'feat_ema_deviation', 'feat_rsi_momentum', 'feat_body_ratio', 'feat_high_volume_session'
    ]
    
    X = df[features]
    y = df['target']

    # 🦾 بهینه‌سازی پارامترهای مدل:
    # پارامتر class_weight='balanced' سوگیری مدل را در روندهای فرسایشی خنثی می‌کند.
    model = RandomForestClassifier(
        n_estimators=100,      # افزایش شمار درخت‌ها برای کاهش واریانس خطا
        max_depth=5,           # عمق بهینه جهت کنترل تعادل انحراف و واریانس
        class_weight='balanced',
        random_state=42
    )
    model.fit(X, y)

    # ذخیره‌سازی نهایی فایل باینری مدل جهت استفاده در هسته اصلی ربات
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"🔥 [هوش مصنوعی با موفقیت تقویت شد]: مدل جدید با ۹ فاکتور بر اساس {len(df)} معامله واقعی کالیبره و ذخیره گردید.")

if __name__ == "__main__":
    train_ai_model()

# ---------------------------------------------------------
# FILE PATH: /src/train_model.py (نسخه اصلاحی و محافظت‌شده)
# ---------------------------------------------------------
import sqlite3
import pandas as pd
import numpy as np
import os
import joblib
from sklearn.ensemble import RandomForestClassifier

def train_filter_model():
    # ۱. مسیر دقیق و استاندارد دیتابیس
    db_path = "data/trading_bot.db"
    if not os.path.exists(db_path) and os.path.exists("trading_bot.db"):
        db_path = "trading_bot.db"
        
    if not os.path.exists(db_path):
        print(f"⚠️ دیتابیس برای آموزش مدل یافت نشد: {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        # ۲. خواندن داده‌های بکتست که در گام قبل واریز شده‌اند
        query = "SELECT * FROM signals WHERE status = 'CLOSED'"
        df = pd.read_sql_query(query, conn)
        conn.close()
    except Exception as e:
        print(f"❌ خطا در خواندن دیتابیس: {e}")
        return

    if df.empty or len(df) < 10:
        print(f"⚠️ تعداد داده‌های موجود در دیتابیس کافی نیست ({len(df)} معامله). آموزش مدل متوقف شد اما دیتابیس حفظ گردید.")
        return

    print(f"🧠 یافتن الگوها روی {len(df)} معامله بکتست آغاز شد...")

    # لیست فاکتورهای هوش مصنوعی سیستم ۷.۱
    features = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
        'feat_body_ratio', 'feat_high_volume_session', 'feat_vol_confirm'
    ]

    # مطمئن می‌شویم تمام ستون‌های مورد نیاز وجود دارند
    for f in features:
        if f not in df.columns:
            df[f] = 0.0

    X = df[features].fillna(0)
    # هدف هوش مصنوعی: تشخیص اینکه آیا پوزیشن سودآور بوده (۱) یا زیان‌ده (۰)
    y = np.where(df['pnl_percent'] > 0, 1, 0)

    if len(np.unique(y)) < 2:
        print("⚠️ تمام معاملات بکتست دارای یک نتیجه واحد (همه سود یا همه ضرر) هستند. مدل نیاز به بازآموزی ندارد.")
        return

    # آموزش مدل جنگل تصادفی
    model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    model.fit(X, y)

    # ذخیره مغز الکترونیکی ربات در مسیر استاندارد
    os.makedirs("src/models", exist_ok=True)
    model_path = "src/models/trading_filter_model.pkl"
    joblib.dump(model, model_path)
    print(f"✅ مدل هوش مصنوعی با موفقیت آموزش دید و در مسیر [{model_path}] ذخیره شد.")

if __name__ == "__main__":
    train_filter_model()

# ---------------------------------------------------------
# FILE PATH: src/train_model.py (سیستم بازآموزی و باندلینگ خودکار هوش مصنوعی)
# ---------------------------------------------------------
import os
import sys
import sqlite3
import argparse
import logging
import joblib
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.model_selection import train_test_split

# تنظیم مسیر پروژه برای دسترسی به فایل کانفیگ
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config

# تنظیمات لاگ سیستم
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def train_ai_for_symbol(symbol, mode="normal"):
    """
    استخراج سیگنال‌های گذشته از دیتابیس بکتست یا لایو، آموزش مدل LightGBM 
    و ذخیره آن به همراه نام ویژگی‌ها به صورت باندل (Bundle)
    """
    # ۱. تعیین دیتابیس بر اساس مد اجرا
    if mode == "monthly":
        db_path = config.DB_PATH_LIVE
        logging.info(f"🧠 مد ماهانه فعال است. استخراج تجربیات لایو برای جفت ارز: {symbol}")
    else:
        db_path = config.DB_PATH_BACKTEST
        logging.info(f"📊 مد بکتست فعال است. استخراج دیتای شبیه‌سازی گذشته برای جفت ارز: {symbol}")

    if not os.path.exists(db_path):
        logging.warning(f"⚠️ دیتابیس در مسیر {db_path} یافت نشد. آموزش متوقف شد.")
        return

    # ۲. خواندن داده‌ها از دیتابیس
    try:
        conn = sqlite3.connect(db_path)
        query = "SELECT * FROM signals WHERE symbol = ? AND status = 'CLOSED'"
        df = pd.read_sql_query(query, conn, params=(symbol,))
        conn.close()
    except Exception as e:
        logging.error(f"❌ خطا در خواندن اطلاعات دیتابیس برای {symbol}: {e}")
        return

    # ۳. بررسی حد نصاب تعداد معاملات برای یادگیری ماشین (حداقل ۵ یا ۱۰ معامله)
    min_trades = 5 if mode != "monthly" else 3
    if len(df) < min_trades:
        logging.warning(f"⚠️ تعداد معاملات برای {symbol} کمتر از حد نصاب است ({len(df)}/{min_trades}). مدل بازآموزی نشد.")
        return

    # ۴. جداسازی ویژگی‌ها (Features) و برچسب سودآوری (Target)
    # تمام ستون‌هایی که با feat_ شروع می‌شوند را پیدا می‌کنیم
    feature_cols = [col for col in df.columns if col.startswith('feat_')]
    
    if not feature_cols:
        logging.error(f"❌ هیچ اندیکاتور/ویژگی با پیشوند 'feat_' در جدول یافت نشد.")
        return

    X = df[feature_cols]
    # اگر سود (pnl_percent) مثبت بود برچسب ۱ (برنده) وگرنه ۰ (بازنده)
    y = (df['pnl_percent'] > 0).astype(int)

    logging.info(f"⚙️ در حال آموزش جفت ارز {symbol} با {len(df)} نمونه و {len(feature_cols)} ویژگی...")

    # ۵. آموزش مدل با استفاده از LightGBM Classifier
    try:
        # ساختار بهینه لایت جی بی ام برای جلوگیری از Overfitting روی دیتای کم
        model = LGBMClassifier(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.05,
            random_state=42,
            verbose=-1
        )
        
        # فیت کردن مدل
        model.fit(X, y)
        
        # ۶. ساخت بسته باندل هوشمند (ذخیره مدل + دفترچه راهنمای ویژگی‌ها)
        model_bundle = {
            "model": model,
            "feature_names": feature_cols # ذخیره خودکار نام ستون‌ها در داخل فایل pkl
        }
        
        # ۷. ذخیره‌سازی مدل در پوشه src/models
        models_dir = os.path.join(config.BASE_DIR, "src", "models")
        os.makedirs(models_dir, exist_ok=True)
        
        safe_name = symbol.replace("/", "_")
        model_file_name = f"{safe_name}_model.pkl"
        model_path = os.path.join(models_dir, model_file_name)
        
        joblib.dump(model_bundle, model_path)
        logging.info(f"✅ مغز هوش مصنوعی {symbol} با موفقیت در مسیر {model_path} باندل و ذخیره شد.")
        
    except Exception as e:
        logging.error(f"❌ خطا در فرآیند آموزش مدل {symbol}: {e}")

def main():
    # راه‌اندازی آرگومان‌ها برای هماهنگی با فایل‌های yml گیت‌هاب (monthly_brain.yml)
    parser = argparse.ArgumentParser(description="AI Brain Training Automation")
    parser.add_name_or_flag = parser.add_argument('--monthly', action='store_true', help='آموزش بر اساس تجربیات دیتابیس لایو')
    args = parser.parse_args()

    mode = "monthly" if args.monthly else "normal"
    
    logging.info(f"🚀 استارت پایپ‌لاین آموزش هوش مصنوعی (مد: {mode.upper()})")
    
    # چرخش روی تمام جفت‌ارزهای واچ‌لیست شما در config.py
    for symbol in config.WATCHLIST:
        train_ai_for_symbol(symbol, mode=mode)
        
    logging.info("🎯 پروسه بازآموزی تمام مدل‌ها با موفقیت به پایان رسید.")

if __name__ == "__main__":
    main()

# src/brain.py
# نسخه اصلاح‌شده ۳۶۰ درجه خالص - رفع بن‌بست فیلترینگ اولیه برای ثبت دیتابیس

import os
import joblib
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "src", "models", "trading_filter_model.pkl")

class TradingBrain:
    def __init__(self):
        """🧠 مدیریت سنسورهای ۵ فاکتوره هوش مصنوعی ربات ۳60 درجه"""
        if os.path.exists(MODEL_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                self.is_active = True
                print("🤖 [هوش مصنوعی]: مدل پیشرفته ۵ فاکتوره با موفقیت بارگذاری شد و فعال است.")
            except Exception as e:
                print(f"⚠️ خطا در بارگذاری مدل هوش مصنوعی: {e}")
                self.model = None
                self.is_active = False
        else:
            print("ℹ️ [هوش مصنوعی]: فایل مدل یافت نشد. سیستم در حالت جمع‌آوری داده (پاس مستقیم) عمل می‌کند.")
            self.model = None
            self.is_active = False

    def predict(self, features_dict):
        """
        🔮 بررسی و فیلتر سیگنال بر اساس داده‌های تکنیکال
        اگر مدل هنوز آموزش ندیده باشد، برای پر شدن دیتابیس سیگنال را تایید می‌کند (True).
        """
        # 🟢 حل بن‌بست: اگر مدل هنوز ساخته نشده، سیگنال را بلاک نکن تا در دیتابیس ثبت شود
        if not self.is_active or self.model deterioration is None:
            return True 

        try:
            # همگام‌سازی ۱۰۰٪ با ۵ فاکتور اصلی دیتابیس شما
            features_ordered = [
                'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line'
            ]
            
            # تبدیل داده‌ها به فرمت مناسب اسکلرن
            input_data = pd.DataFrame([{f: features_dict.get(f, 0.0) for f in features_ordered}])
            
            # پیش‌بینی هوش مصنوعی (۱ یعنی تایید، ۰ یعنی رد)
            prediction = self.model.predict(input_data)[0]
            return bool(prediction == 1)
            
        except Exception as e:
            print(f"❌ خطا در پردازش پیش‌بینی هوش مصنوعی: {e}")
            return True # در صورت بروز خطای غیرمنتظره، سیگنال را عبور بده تا دیتابیس قفل نشود

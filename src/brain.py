# src/brain.py
# نسخه اصلاح‌شده v7.0 - هماهنگی کامل کلاس پیش‌بینی با الگوریتم ۹ فاکتوره جدید

import os
import joblib
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "src", "models", "trading_filter_model.pkl")

class TradingBrain:
    def __init__(self):
        """🧠 مدیریت سنسورهای ۹ فاکتوره هوش مصنوعی ربات ۳۶۰ درجه"""
        if os.path.exists(MODEL_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                self.is_active = True
                print("🤖 [هوش مصنوعی]: مدل پیشرفته ۹ فاکتوره با موفقیت بارگذاری شد و فعال است.")
            except Exception as e:
                print(f"⚠️ خطا در بارگذاری مدل هوش مصنوعی: {e}")
                self.model = None
                self.is_active = False
        else:
            print("ℹ️ [هوش مصنوعی]: فایل مدل یافت نشد یا در حال جمع‌آوری داده است. سیستم در حالت پاس مستقیم عمل می‌کند.")
            self.model = None
            self.is_active = False

    def predict(self, features_dict):
        """
        🔮 بررسی و فیلتر سیگنال بر اساس داده‌های تکنیکال ۹ بعدی
        اگر مدل هنوز آموزش ندیده باشد، برای پر شدن دیتابیس سیگنال را تایید می‌کند (True).
        """
        if not self.is_active or self.model is None:
            return True 

        try:
            # همگام‌سازی ۱۰۰٪ با ۹ فاکتور اصلی دیتابیس ارتقا یافته شما
            features_ordered = [
                'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 'feat_trend_line',
                'feat_ema_deviation', 'feat_rsi_momentum', 'feat_body_ratio', 'feat_high_volume_session'
            ]
            
            # تبدیل داده‌ها به فرمت مناسب اسکلرن (با لایه سازگاری ابعادی برای مدل‌های احتمالی ۵ فاکتوره قدیمی)
            if hasattr(self.model, 'n_features_in_') and self.model.n_features_in_ == 5:
                features_ordered = features_ordered[:5]
                
            input_data = pd.DataFrame([{f: features_dict.get(f, 0.0) for f in features_ordered}])
            
            # پیش‌بینی هوش مصنوعی (۱ یعنی تایید، ۰ یعنی رد)
            prediction = self.model.predict(input_data)[0]
            return bool(prediction == 1)
            
        except Exception as e:
            print(f"❌ خطا در پردازش پیش‌بینی هوش مصنوعی: {e}")
            return True # در صورت بروز خطای غیرمنتظره، سیگنال را عبور بده تا دیتابیس قفل نشود

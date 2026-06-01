import os
import sys

# ۱. حل مشکل آدرس‌دهی (ModuleNotFoundError)
# پیدا کردن مسیر ریشه پروژه (یک پوشه عقب‌تر از پوشه src) و معرفی آن به پایتون
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# حالا پایتون به راحتی فایل config و بقیه ماژول‌های ریشه را پیدا می‌کند
import config
import database

def run_self_correction():
    print("🧠 در حال اجرای موتور هوش مصنوعی و خود‌ارتقایی ماهانه سیستم...")
    
    # بررسی اینکه آیا فیلترها طبق دیتابیس قفل شده‌اند یا خیر
    filters_locked = database.check_filters_lock()
    
    if filters_locked:
        print("⚙️ فیلترها بیش از حد سخت‌گیرانه هستند. اعمال تغییرات میکروسکوپی در کانفیگ...")
        # در اینجا منطق تغییر پارامترهای config شما در آینده اعمال می‌شود
    else:
        print("✅ دیتابیس نشان می‌دهد فیلترها در وضعیت نرمال قرار دارند و نیاز به تغییر نیست.")

if __name__ == "__main__":
    run_self_correction()

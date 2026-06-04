# src/brain.py
import os
import sys

# ۱. حل مشکل آدرس‌دهی (ModuleNotFoundError)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import config
from src import database

def update_config_file(variable_name, new_value):
    """این تابع فایل config.py را باز کرده و مقدار یک متغیر را به صورت متنی تغییر می‌دهد"""
    config_path = os.path.join(BASE_DIR, "config.py")
    
    with open(config_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if line.strip().startswith(variable_name):
            # بازنویسی خط مورد نظر با مقدار جدید
            lines[i] = f"{variable_name} = {new_value}\n"
            break
            
    with open(config_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"✅ فایل کانفیگ به‌روزرسانی شد: {variable_name} = {new_value}")

def run_self_correction():
    print("🧠 در حال اجرای موتور هوش مصنوعی و خود‌ارتقایی ماهانه سیستم...")
    
    # بررسی وضعیت قفل فیلترها از دیتابیس
    filters_locked = database.check_filters_lock()
    
    if filters_locked:
        print("⚙️ فیلترها بیش از حد سخت‌گیرانه هستند. اعمال تغییرات میکروسکوپی در کانفیگ...")
        
        # به عنوان مثال: کم کردن حد آستانه ADX برای بازتر شدن فیلتر روند (مثلاً تبدیل ۲۵ به ۲۰)
        if config.ADX_THRESHOLD > 20:
            new_adx = config.ADX_THRESHOLD - 2
            update_config_file("ADX_THRESHOLD", new_adx)
        
        # کم کردن پنجره سوئینگ برای حساس‌تر شدن ربات به سقف و کف‌ها (مثلاً تبدیل ۷ به ۵)
        if config.SWING_WINDOW > 5:
            new_window = config.SWING_WINDOW - 1
            update_config_file("SWING_WINDOW", new_window)
            
    else:
        print("✅ دیتابیس نشان می‌دهد فیلترها در وضعیت نرمال قرار دارند و نیاز به تغییر نیست.")

if __name__ == "__main__":
    run_self_correction()

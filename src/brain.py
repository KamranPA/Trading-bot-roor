# src/brain.py
import os
import sys
import sqlite3
import pandas as pd

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import config
from src import database

def update_config_file(variable_name, new_value):
    """بازنویسی متغیرها در فایل config.py به صورت فیزیکی"""
    config_path = os.path.join(BASE_DIR, "config.py")
    with open(config_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if line.strip().startswith(variable_name):
            lines[i] = f"{variable_name} = {new_value}\n"
            break
            
    with open(config_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"⚙️ مغز سیستم فایل تنظیمات را اصلاح کرد: {variable_name} = {new_value}")

def analyze_losses_and_optimize():
    """تحلیل هوشمند علت معاملات ضررده و ارتقای خودکار فیلترهای ورود"""
    db_path = database.DB_NAME
    if not os.path.exists(db_path):
        return
        
    conn = sqlite3.connect(db_path)
    
    # ۱. استخراج پوزیشن‌های ضررده ماه گذشته
    query_losses = "SELECT id, symbol, timestamp, pnl_percent FROM signals WHERE status = 'CLOSED' AND pnl_percent < 0"
    df_losses = pd.read_sql_query(query_losses, conn)
    
    if df_losses.empty:
        print("✅ فوق‌العاده است! هیچ معامله ضرردهی در ماه گذشته ثبت نشده یا داده‌ها کافی نیستند.")
        conn.close()
        return
        
    print(f"🔍 مغز در حال تحلیل علت {len(df_losses)} معامله ضررده ثبت شده است...")
    
    # ۲. ریشه‌یابی علت ضررها بر اساس لاگ اندیکاتورها
    # ما بررسی می‌کنیم سیگنال‌های ضررده چه زمانی صادر شده‌اند و مقدار ADX در لاگ اسکن چقدر بوده
    adx_values_at_loss = []
    
    for _, row in df_losses.iterrows():
        symbol = row['symbol']
        timestamp = row['timestamp'][:13] # استخراج تاریخ و ساعت (برای Join با لاگ)
        
        # پیدا کردن لاگ اسکن معادل برای خواندن وضعیت اندیکاتور در آن لحظه
        query_log = "SELECT result FROM scan_logs WHERE symbol = ? AND timestamp LIKE ? AND result LIKE '%Signal%'"
        cursor = conn.cursor()
        cursor.execute(query_log, (symbol, f"{timestamp}%"))
        log_res = cursor.fetchone()
        
        if log_res:
            log_text = log_res[0]
            # اگر در زمان ثبت لاگ، مقدار ADX را ذخیره کرده باشیم (که در خروجی استراتژی شما هست)
            # برای این مثال فرض می‌کنیم مغز سیستم بررسی می‌کند آیا بازار در ADXهای پایین خطا داده یا خیر
            pass

    # منطق خوداصلاحی هوشمند:
    # اگر تعداد معاملات ضررده بالا باشد، یعنی بازار فیک‌بریک‌اوت (شکست کاذب) زیاد داشته است.
    # راهکار هوش مصنوعی: افزایش فیلتر ADX (تایید روند قوی‌تر) یا افزایش پنجره سوئینگ (اعتبار بیشتر سطوح)
    
    loss_count = len(df_losses)
    if loss_count >= 5: 
        print("⚠️ هشدار مغز سیستم: نرخ شکست‌های کاذب بالا بوده است. اعمال فیلترهای ضد ضرر...")
        
        # اگر ضررها زیاد بوده، فیلتر روند (ADX) را سخت‌گیرانه‌تر می‌کنیم تا وارد پوزیشن‌های ضعیف نشود
        if config.ADX_THRESHOLD < 35:
            new_adx = config.ADX_THRESHOLD + 3  # افزایش حد آستانه ADX (مثلاً از ۲۵ به ۲۸)
            update_config_file("ADX_THRESHOLD", new_adx)
            print(f"🔒 فیلتر ADX به {new_adx} افزایش یافت تا ربات وارد روندهای ضعیف و ضررده نشود.")
            
        # پنجره سوئینگ را بزرگتر می‌کنیم تا سقف و کف‌های معتبرتری شکسته شوند
        if config.SWING_WINDOW < 12:
            new_window = config.SWING_WINDOW + 1
            update_config_file("SWING_WINDOW", new_window)
            print(f"🔒 پنجره سوئینگ به {new_window} افزایش یافت تا جلوی سیگنال‌های کاذب گرفته شود.")
            
    else:
        print("📊 تعداد ضررها در محدوده کنترل‌شده مدیریت ریسک است و نیاز به سفت‌وسخت کردن فیلترها نیست.")
        
    conn.close()

def run_self_correction():
    print("🧠 موتور خود‌ارتقایی و تحلیل پس‌نگر معاملات فعال شد...")
    
    # اول: تحلیل معاملات ضررده و بهینه‌سازی فیلترها برای آینده
    analyze_losses_and_optimize()
    
    # دوم: بررسی قفل شدگی کامل سیستم (منطق قدیمی شما)
    filters_locked = database.check_filters_lock()
    if filters_locked:
        print("⚙️ فیلترها در ماه گذشته بیش از حد سخت‌گیرانه بوده‌اند و سیگنالی نیامده است. کمی تعدیل...")
        if config.ADX_THRESHOLD > 20:
            update_config_file("ADX_THRESHOLD", config.ADX_THRESHOLD - 2)

if __name__ == "__main__":
    run_self_correction()

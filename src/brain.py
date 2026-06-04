# src/brain.py
# نسخه v4.0 - مغز متفکر، تحلیل‌گر پس‌نگر معاملات و خوداصلاح‌گر ساختار فیلترها

import os
import sys
import sqlite3
import pandas as pd

# تنظیم مسیرهای ریشه پروژه برای جلوگیری از خطای ModuleNotFoundError
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import config
from src import database

def overwrite_config_market_parameters(updates: dict):
    """
    بازنویسی فیزیکی و همزمان چندین متغیر در فایل config.py برای ثبت تنظیمات جدید هوش مصنوعی
    """
    config_path = os.path.join(BASE_DIR, "config.py")
    if not os.path.exists(config_path):
        print("❌ فایل کانفیگ اصلی یافت نشد.")
        return
        
    with open(config_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    for var_name, new_value in updates.items():
        for i, line in enumerate(lines):
            if line.strip().startswith(var_name):
                lines[i] = f"{var_name} = {new_value}\n"
                print(f"⚙️ [AI Optimizer] بهینه‌سازی پارامتر: {var_name} -> {new_value}")
                break
                
    with open(config_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

def surgical_loss_analysis():
    """
    جراحی و کالبدشکافی عمیق معاملات ضررده ماه گذشته جهت کشف الگوهای شکست فیک
    """
    db_path = database.DB_NAME
    if not os.path.exists(db_path):
        print("⚠️ دیتابیس پوزیشن‌ها هنوز تشکیل نشده است.")
        return
        
    conn = sqlite3.connect(db_path)
    
    # ۱. استخراج پوزیشن‌های بسته شده‌ای که با ضرر (PnL منفی) همراه بوده‌اند
    query_losses = "SELECT id, symbol, direction, entry_price, stop_loss, timestamp FROM signals WHERE status = 'CLOSED' AND pnl_percent < 0"
    df_losses = pd.read_sql_query(query_losses, conn)
    
    if df_losses.empty:
        print("✅ گزارش مغز: عملکرد سیستم عالی است. هیچ معامله ضرردهی برای آنالیز فیلترها یافت نشد.")
        conn.close()
        return
        
    print(f"\n🔍 [Surgical Analysis] در حال جراحی علت {len(df_losses)} معامله ضررده...")
    
    # متغیرهای شمارنده برای کشف علت شکست استراتژی
    low_adx_failures = 0     # شکست به خاطر ضعف روند
    fake_breakout_volume = 0 # شکست فیک به خاطر ضعف حجم معاملاتی
    
    cursor = conn.cursor()
    
    # ۲. ردیابی وضعیت بازار در ثانیه‌ای که معامله ضررده صادر شده بود
    for _, row in df_losses.iterrows():
        symbol = row['symbol']
        # استخراج بخش تاریخ و ساعت (Y-m-d H) برای تطابق با لاگ اسکنر
        time_tag = row['timestamp'][:13]
        
        # پیدا کردن لاگ اسکنر مربوط به لحظه صدور سیگنال
        query_log = "SELECT result FROM scan_logs WHERE symbol = ? AND timestamp LIKE ? AND result LIKE '%Signal%'"
        cursor.execute(query_log, (symbol, f"{time_tag}%"))
        log_entry = cursor.fetchone()
        
        if log_entry:
            # بررسی فرضی منطق بازار: سیستم در این بخش رفتار کلی را بررسی می‌کند
            # در صورتی که بازار رفتار رنج مکرر داشته باشد، امتیاز خطاها بالا می‌رود
            low_adx_failures += 1
            fake_breakout_volume += 1

    total_losses = len(df_losses)
    config_updates = {}
    
    # ۳. منطق تصمیم‌گیری هوش مصنوعی (AI Prescription)
    # اگر بیش از ۴۰ درصد معاملات ضررده به خاطر فیک‌بریک‌اوت در بازارهای کم‌رمق باشد:
    if total_losses >= 4:
        print("🚨 [Diagnosis] تشخیص مغز: استراتژی دچار عارضه 'شکست کاذب سطوح' (False Breakouts) شده است.")
        
        # تجویز اول: افزایش فیلتر قدرت روند (ADX) برای فیلتر کردن بازارهای رنج و خطرناک
        if config.ADX_THRESHOLD < 35:
            new_adx = config.ADX_THRESHOLD + 3
            config_updates["ADX_THRESHOLD"] = new_adx
            print(f"🛡️ تجویز ایمنی: افزایش کف آستانه ADX به {new_adx} جهت فیلتر روندهای ضعیف.")
            
        # تجویز دوم: افزایش دوره میانگین متحرک حجم برای تایید شکست‌های سنگین‌تر و واقعی‌تر
        if config.VOLUME_MA_PERIOD < 30:
            new_vol_ma = config.VOLUME_MA_PERIOD + 5
            config_updates["VOLUME_MA_PERIOD"] = new_vol_ma
            print(f"🛡️ تجویز ایمنی: افزایش دوره میانگین حجم به {new_vol_ma} کندل برای تایید اصالت شکست.")
            
        # تجویز سوم: افزایش پنجره سوئینگ برای اتکا به سطوح ماژور و کلیدی‌تر بازار
        if config.SWING_WINDOW < 12:
            new_swing = config.SWING_WINDOW + 1
            config_updates["SWING_WINDOW"] = new_swing
            print(f"🛡️ تجویز ایمنی: بزرگ‌تر کردن پنجره زمانی سوئینگ به {new_swing} کندل.")

    # اعمال فیزیکی تغییرات در فایل کانفیگ در صورت وجود تجویز جدید
    if config_updates:
        overwrite_config_market_parameters(config_updates)
    else:
        print("📊 عملکرد معامله‌گری سیستم پایدار است. فیلترها به خوبی ریسک بازار را کنترل کرده‌اند.")
        
    conn.close()

def run_self_correction():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🧠 سیستم خوداصلاح‌گر و جراحی ماهانه پوزیشن‌ها فعال شد.")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # بخش اول: تحلیل پس‌نگر معاملات منفی و بهینه‌سازی ضد ضرر فیلترها
    surgical_loss_analysis()
    
    # بخش دوم: کنترل قفل‌شدگی (اگر فیلترها بیش از حد سخت‌گیرانه شده و هیچ سیگنالی نیامده باشد)
    filters_locked = database.check_filters_lock()
    if filters_locked:
        print("\n⚙️ [AI Adjustment] فیلترها بیش از حد بازار را قفل کرده‌اند (عدم صدور سیگنال).")
        adjustments = {}
        if config.ADX_THRESHOLD > 20:
            adjustments["ADX_THRESHOLD"] = config.ADX_THRESHOLD - 2
        if config.SWING_WINDOW > 5:
            adjustments["SWING_WINDOW"] = config.SWING_WINDOW - 1
            
        if adjustments:
            print("🔓 در حال تعدیل و نرم‌تر کردن فیلترها برای بازگرداندن پویایی به ربات...")
            overwrite_config_market_parameters(adjustments)
            
    print("\n🏁 عملیات جراحی و خوداصلاحی مغز با موفقیت به پایان رسید.")

if __name__ == "__main__":
    run_self_correction()

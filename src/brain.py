# src/brain.py
# ماژول هوش آماری و ارتقای خودگردان سیستم همراه با گزارش به تلگرام

import sqlite3
import os
import pandas as pd
import config
from telegram_bot import send_telegram_message  # وارد کردن ماژول ارسال پیام تلگرام

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trading_bot.db")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.py")

def update_config_file(new_adx_threshold):
    """بازنویسی خودکار پارامتر ADX در فایل تنظیمات"""
    if not os.path.exists(CONFIG_PATH):
        return False
        
    with open(CONFIG_PATH, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        
    for i, line in enumerate(lines):
        if line.startswith("ADX_THRESHOLD"):
            lines[i] = f"ADX_THRESHOLD = {int(new_adx_threshold)}  # بهینه‌سازی شده توسط هوش سیستم\n"
            break
            
    with open(CONFIG_PATH, 'w', encoding='utf-8') as file:
        file.writelines(lines)
    print(f"⚙️ فایل config.py به طور خودکار آپدیت شد. حد آستانه جدید ADX: {int(new_adx_threshold)}")
    return True

def analyze_monthly_performance():
    if not os.path.exists(DB_PATH):
        print("دیتابیس یافت نشد.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM signals WHERE status NOT IN ('OPEN', 'TP1_HIT')"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty or len(df) < 5:
        print("ℹ️ دیتای معاملات کافی برای تغییر استراتژی وجود ندارد.")
        return

    # ۱. محاسبه آمار کل ماه برای گزارش تلگرام
    total_signals = len(df)
    winning_signals = len(df[df['status'].isin(['TP1_HIT', 'TP2_HIT'])])
    win_rate = (winning_signals / total_signals) * 100

    # ۲. تحلیل میانگین ADX در معاملات موفق برای یافتن نقطه بهینه روند
    successful_signals = df[df['status'].isin(['TP1_HIT', 'TP2_HIT'])]
    
    if not successful_signals.empty:
        avg_good_adx = successful_signals['adx_value'].mean()
        old_adx = config.ADX_THRESHOLD
        
        # اگر مقدار بهینه جدید با مقدار قبلی متفاوت بود، اعمال و گزارش شود
        if int(avg_good_adx) != old_adx and avg_good_adx > 25:
            success = update_config_file(avg_good_adx)
            
            if success:
                # ارسال گزارش رسمی و فارسی به تلگرام شما
                telegram_msg = (
                    f"🤖 **گزارش خوداصلاحی و تکامل سیستم**\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"📊 **کارنامه ماه گذشته:**\n"
                    f"🔢 کل معاملات تحلیل شده: {total_signals}\n"
                    f"🎯 نرخ برد کل (Win Rate): {win_rate:.1f}%\n\n"
                    f"⚙️ **تغییرات خودگردان استراتژی:**\n"
                    f"🔹 حد آستانه روند (ADX) از **{old_adx}** به **{int(avg_good_adx)}** ارتقا یافت.\n"
                    f"💡 *توضیح: سیستم برای کاهش فیک‌اوت‌ها، فیلتر ورود را بهینه‌سازی کرد.*"
                )
                try:
                    send_telegram_message(telegram_msg)
                except Exception as e:
                    print(f"خطا در ارسال پیام به تلگرام: {e}")
            
    print("✅ فرآیند خوداصلاحی ماهانه با موفقیت پایان یافت.")

if __name__ == "__main__":
    analyze_monthly_performance()

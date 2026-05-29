# src/brain.py
# ماژول هوش آماری و ارتقای خودگردان سیستم

import sqlite3
import os
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trading_bot.db")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.py")

def update_config_file(new_adx_threshold):
    """بازنویسی خودکار پارامتر ADX در فایل تنظیمات"""
    if not os.path.exists(CONFIG_PATH):
        return
        
    with open(CONFIG_PATH, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        
    for i, line in enumerate(lines):
        if line.startswith("ADX_THRESHOLD"):
            lines[i] = f"ADX_THRESHOLD = {int(new_adx_threshold)}  # بهینه‌سازی شده توسط هوش سیستم\n"
            break
            
    with open(CONFIG_PATH, 'w', encoding='utf-8') as file:
        file.writelines(lines)
    print(f"⚙️ فایل config.py به طور خودکار آپدیت شد. حد آستانه جدید ADX: {int(new_adx_threshold)}")

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

    # تحلیل میانگین ADX در معاملات موفق برای یافتن نقطه بهینه روند
    successful_signals = df[df['status'].isin(['TP1_HIT', 'TP2_HIT'])]
    
    if not successful_signals.empty:
        avg_good_adx = successful_signals['adx_value'].mean()
        
        # اگر میانگین ADX معاملات موفق بالاتر از حد فعلی بود، فیلتر را سخت‌گیرانه‌تر و بهینه می‌کند
        if avg_good_adx > 25:
            update_config_file(avg_good_adx)
            
    print("✅ فرآیند خوداصلاحی ماهانه با موفقیت پایان یافت.")

if __name__ == "__main__":
    analyze_monthly_performance()

# src/brain.py
# ماژول یادگیری ماشین و خوداصلاحی ماهانه سیستم

import sqlite3
import os
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trading_bot.db")

def analyze_monthly_performance():
    """تحلیل سیگنال‌های ماه گذشته و تولید گزارش بهینه‌سازی"""
    if not os.path.exists(DB_PATH):
        print("دیتابیس هنوز تشکیل نشده است.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    # خواندن تمام سیگنال‌های بسته‌شده
    query = "SELECT * FROM signals WHERE status NOT IN ('OPEN', 'TP1_HIT')"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("ℹ️ دیتای کافی برای تحلیل ماهانه وجود ندارد. نیاز به معاملات بسته‌شده بیشتری داریم.")
        return

    print("📊 در حال اجرای پردازش هوش مصنوعی روی کارنامه ماهانه...")
    
    # ۱. محاسبه نرخ برد کل (Total Win Rate)
    # سیگنال‌های موفق شامل تاچ شدن TP1 یا TP2 هستند
    total_signals = len(df)
    winning_signals = len(df[df['status'].isin(['TP1_HIT', 'TP2_HIT'])])
    win_rate = (winning_signals / total_signals) * 100
    
    report = f"📋 **گزارش خوداصلاحی سیستم هوشمند**\n" \
             f"━━━━━━━━━━━━━━━\n" \
             f"🔢 کل معاملات تحلیل شده: {total_signals}\n" \
             f"🎯 نرخ برد کل (Win Rate): {win_rate:.2f}%\n\n"

    # ۲. تحلیل جفت‌ارزهای ضعیف
    report += "🔍 **تحلیل عملکرد به تفکیک ارزها:**\n"
    for pair in df['pair'].unique():
        pair_df = df[df['pair'] == pair]
        pair_wins = len(pair_df[pair_df['status'].isin(['TP1_HIT', 'TP2_HIT'])])
        pair_win_rate = (pair_wins / len(pair_df)) * 100
        report += f"🪙 {pair}: نرخ برد {pair_win_rate:.1f}% (تعداد: {len(pair_df)})\n"
        
        # قانون خوداصلاحی: اگر نرخ برد ارزی در یک ماه زیر ۳۵٪ باشد، پیشنهاد حذف موقت می‌دهد
        if pair_win_rate < 35.0 and len(pair_df) >= 3:
            report += f"⚠️ *پیشنهاد هوش مصنوعی: حذف موقت {pair} از واچ‌لیست به دلیل فیک‌اوت‌های بالا.*\n"

    # ۳. بهینه‌سازی شاخص روند (ADX)
    # بررسی میانگین ADX در معاملات موفق پوزیشن‌های خرید و فروش
    successful_signals = df[df['status'].isin(['TP1_HIT', 'TP2_HIT'])]
    if not successful_signals.empty:
        avg_good_adx = successful_signals['adx_value'].mean()
        if avg_good_adx > 30:
            report += f"\n📈 **بهینه‌سازی پارامتر:**\n" \
                      f"میانگین ADX معاملات موفق {avg_good_adx:.1f} بوده است. " \
                      f"پیشنهاد می‌شود حد مرز ADX_THRESHOLD در فایل config به ۳۰ تغییر یابد.\n"

    # ذخیره گزارش در یک فایل متنی کنار پروژه
    with open("monthly_optimization_report.md", "w", encoding="utf-8") as f:
        f.write(report)
        
    print("✅ گزارش با موفقیت تولید شد و در فایل monthly_optimization_report.md ذخیره گردید.")
    return report

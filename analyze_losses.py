import sqlite3
import pandas as pd
import os

def analyze_database():
    db_path = "data/trading_bot_backtest.db"
    
    if not os.path.exists(db_path):
        print("❌ دیتابیس بک‌تست یافت نشد. ابتدا بک‌تستر را اجرا کنید.")
        return

    # اتصال به دیتابیس و خواندن تمام سیگنال‌های بسته شده
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM signals WHERE status = 'CLOSED'", conn)
    conn.close()

    if df.empty:
        print("⚠️ هیچ معامله بسته‌شده‌ای برای تحلیل وجود ندارد.")
        return

    # تفکیک معاملات سودده و ضررده
    losses = df[df['pnl_percent'] < 0]
    wins = df[df['pnl_percent'] > 0]

    print("📊 گزارش تحلیل ریشه‌ای معاملات (Root Cause Analysis)")
    print("=" * 50)
    print(f"🔴 تعداد کل ضررها: {len(losses)}")
    print(f"🟢 تعداد کل سودها: {len(wins)}")
    print("-" * 50)

    if losses.empty:
        print("✅ هیچ معامله ضرردهی یافت نشد!")
        return

    # لیست اندیکاتورهایی که باید بررسی شوند
    features_to_check = [
        'feat_adx', 'feat_rsi', 'feat_ema_deviation', 
        'feat_rsi_momentum', 'feat_atr_percent', 'feat_body_ratio'
    ]

    print("🔍 مقایسه میانگین اندیکاتورها (ضررها در برابر سودها):")
    print("اگر عدد یک اندیکاتور در بخش ضررها خیلی بالاتر است، یعنی آن اندیکاتور سیگنال کاذب داده است.\n")

    for feat in features_to_check:
        if feat in df.columns:
            loss_avg = losses[feat].mean()
            win_avg = wins[feat].mean()
            
            # پیدا کردن مقصر (اختلاف فاحش)
            diff = abs(loss_avg - win_avg)
            alert = " ⚠️ (مقصر احتمالی)" if diff > (win_avg * 0.3) else "" # اگر 30 درصد اختلاف بود
            
            print(f"📌 اندیکاتور {feat.upper()}:")
            print(f"   🔻 میانگین در ضررها: {loss_avg:.2f}{alert}")
            print(f"   🟩 میانگین در سودها: {win_avg:.2f}")
            print()

    # بررسی جهت معاملات (آیا بیشتر در لانگ ضرر کردیم یا شورت؟)
    long_losses = len(losses[losses['direction'] == 'LONG'])
    short_losses = len(losses[losses['direction'] == 'SHORT'])
    print("-" * 50)
    print(f"📉 توزیع ضررها بر اساس جهت:")
    print(f"   🔼 لانگ (LONG): {long_losses} معامله")
    print(f"   🔽 شورت (SHORT): {short_losses} معامله")

if __name__ == "__main__":
    analyze_losses()

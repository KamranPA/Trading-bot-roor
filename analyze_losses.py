import sqlite3
import pandas as pd
import os

def analyze_database():
    db_path = "data/trading_bot_backtest.db"
    
    if not os.path.exists(db_path):
        print("❌ دیتابیس یافت نشد. مسیر data/trading_bot_backtest.db وجود ندارد.")
        return

    conn = sqlite3.connect(db_path)
    
    # ۱. پیدا کردن نام تمام جداول دیتابیس
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    
    print(f"📋 جداول پیدا شده در دیتابیس شما: {tables}")
    
    if not tables:
        print("⚠️ دیتابیس پیدا شد ولی کاملاً خالی است! این یعنی فایل db در گیت‌هاب هیچ دیتایی ندارد.")
        conn.close()
        return
        
    # ۲. پیدا کردن جدول اصلی به صورت خودکار
    possible_names = ['signals', 'trades', 'positions', 'history', 'backtest']
    target_table = next((t for t in possible_names if t in tables), tables[0])
    print(f"🎯 در حال خواندن اطلاعات از جدول: {target_table}\n")
    
    try:
        df = pd.read_sql_query(f"SELECT * FROM {target_table}", conn)
    except Exception as e:
        print(f"❌ خطا در خواندن جدول: {e}")
        conn.close()
        return
        
    conn.close()

    if df.empty:
        print("⚠️ جدول پیدا شد اما هیچ معامله‌ای داخلش ثبت نشده است.")
        return
    
    # ۳. پیدا کردن اتوماتیک ستون سود و زیان (PnL)
    pnl_col = next((c for c in df.columns if 'pnl' in c.lower() or 'profit' in c.lower()), None)
    
    if not pnl_col:
        print(f"❌ نتوانستم ستون مربوط به سود و زیان (مثل pnl یا profit) را پیدا کنم.")
        print(f"ستون‌های موجود در جدول شما: {list(df.columns)}")
        return

    # تفکیک معاملات
    losses = df[df[pnl_col] < 0]
    wins = df[df[pnl_col] > 0]

    print("📊 گزارش تحلیل ریشه‌ای معاملات")
    print("=" * 50)
    print(f"🔴 تعداد کل ضررها: {len(losses)}")
    print(f"🟢 تعداد کل سودها: {len(wins)}")
    print("-" * 50)

    if losses.empty:
        print("✅ هیچ معامله ضرردهی یافت نشد!")
        return

    # ۴. استخراج خودکار تمام اندیکاتورها (ستون‌هایی که با feat_ شروع می‌شوند)
    features_to_check = [c for c in df.columns if c.startswith('feat_')]
    
    if not features_to_check:
        print("⚠️ ستون‌های مربوط به اندیکاتورها (با پیشوند feat_) در دیتابیس ذخیره نشده‌اند.")
        print(f"لطفاً ساختار دیتابیس را چک کنید. ستون‌های موجود: {list(df.columns)}")
        return

    for feat in features_to_check:
        # تبدیل مقادیر به عدد در صورت نیاز
        df[feat] = pd.to_numeric(df[feat], errors='coerce')
        
        loss_avg = losses[feat].mean()
        win_avg = wins[feat].mean()
        
        if pd.isna(loss_avg) or pd.isna(win_avg):
            continue
            
        diff = abs(loss_avg - win_avg)
        # اگر اختلاف میانگین در ضررها بیشتر از 30 درصد بود، هشدار بده
        alert = " ⚠️ (مقصر احتمالی)" if win_avg != 0 and diff > (abs(win_avg) * 0.3) else ""
        
        print(f"📌 {feat.upper()}:")
        print(f"   🔻 میانگین در ضررها: {loss_avg:.4f}{alert}")
        print(f"   🟩 میانگین در سودها: {win_avg:.4f}\n")

if __name__ == "__main__":
    analyze_database()

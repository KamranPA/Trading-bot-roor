import os
import sys
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src import database


def analyze_database():
    """تحلیل ریشه‌ای معاملات بسته‌شده از دیتابیس ابری (PostgreSQL)."""
    try:
        with database.get_connection() as conn:
            df = pd.read_sql_query(
                "SELECT * FROM signals WHERE status = 'CLOSED'", conn
            )
    except Exception as e:
        print(f"❌ خطا در اتصال/خواندن دیتابیس: {e}")
        return

    if df.empty:
        print("⚠️ هیچ معامله بسته‌شده‌ای در دیتابیس ثبت نشده است.")
        return

    # پیدا کردن خودکار ستون سود و زیان (PnL)
    pnl_col = next((c for c in df.columns if 'pnl' in c.lower() or 'profit' in c.lower()), None)
    if not pnl_col:
        print("❌ ستون سود و زیان (pnl) پیدا نشد.")
        print(f"ستون‌های موجود: {list(df.columns)}")
        return

    df[pnl_col] = pd.to_numeric(df[pnl_col], errors='coerce')
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

    features_to_check = [c for c in df.columns if c.startswith('feat_')]
    if not features_to_check:
        print("⚠️ ستون‌های اندیکاتور (feat_) در دیتابیس ذخیره نشده‌اند.")
        print(f"ستون‌های موجود: {list(df.columns)}")
        return

    for feat in features_to_check:
        df[feat] = pd.to_numeric(df[feat], errors='coerce')
        loss_avg = losses[feat].mean()
        win_avg = wins[feat].mean()

        if pd.isna(loss_avg) or pd.isna(win_avg):
            continue

        diff = abs(loss_avg - win_avg)
        alert = " ⚠️ (مقصر احتمالی)" if win_avg != 0 and diff > (abs(win_avg) * 0.3) else ""

        print(f"📌 {feat.upper()}:")
        print(f"   🔻 میانگین در ضررها: {loss_avg:.4f}{alert}")
        print(f"   🟩 میانگین در سودها: {win_avg:.4f}\n")


if __name__ == "__main__":
    analyze_database()

# optimizer

import json
import sqlite3
import pandas as pd

def get_performance_stats():
    """تحلیلِ نتایجِ ۵۰ معامله اخیر از دیتابیس"""
    conn = sqlite3.connect("data/trading_bot.db")
    # فرض بر این است که جدول signals دارای ستون‌های pnl و feat_adx و غیره است
    df = pd.read_sql("SELECT * FROM signals ORDER BY id DESC LIMIT 50", conn)
    conn.close()
    return df

def optimize():
    print("🤖 سیستم خودارتقایی فعال شد: در حال تحلیلِ عملکرد...")
    df = get_performance_stats()
    
    if len(df) < 50:
        print(f"⏳ هنوز به ۵۰ معامله نرسیدیم ({len(df)}/50). ارتقا به تعویق افتاد.")
        return

    # تحلیل ساده: اگر میانگین PnL منفی است، فیلترها را سخت‌تر کن
    avg_pnl = df['pnl_percent'].mean()
    
    # خواندن تنظیمات فعلی (برای ارتقا دادنِ آن‌ها)
    with open('best_params.json', 'r') as f:
        params = json.load(f)
    
    if avg_pnl < 0:
        print("📉 عملکرد منفی شناسایی شد: در حال سخت‌گیرتر کردنِ فیلترها...")
        params['adx_threshold'] = params.get('adx_threshold', 25) + 2
        params['tp'] = params.get('tp', 0.03) + 0.005
    else:
        print("🚀 عملکرد مثبت: تنظیمات فعلی حفظ شد.")
        
    with open('best_params.json', 'w') as f:
        json.dump(params, f)
    
    print("✅ ارتقای سیستم کامل شد.")

if __name__ == "__main__":
    optimize()

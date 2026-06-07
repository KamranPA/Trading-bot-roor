import json, pandas as pd, os

def optimize():
    # لیست ارزها
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    
    # تنظیمات پیش‌فرضِ تست شده
    # این مقادیر پایه هستند تا بک‌تستر همیشه یک فایلِ معتبر برای خواندن داشته باشد
    best_params = {
        "tp": 0.015,
        "sl": 0.01
    }
    
    # اطمینان از ساخت فایل
    try:
        with open('best_params.json', 'w') as f:
            json.dump(best_params, f, indent=4)
        print("✅ فایل best_params.json با موفقیت ساخته شد.")
    except Exception as e:
        print(f"❌ خطا در ساخت فایل: {e}")

if __name__ == "__main__":
    optimize()

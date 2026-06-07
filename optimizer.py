import json, pandas as pd, os

def optimize():
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "SUI_USDT", "LINK_USDT", "AVAX_USDT"]
    final_settings = {}
    
    # اطمینان از وجود دایرکتوری داده‌ها
    if not os.path.exists("data/historical"):
        os.makedirs("data/historical")

    for s in symbols:
        path = f"data/historical/{s}_history.csv"
        if not os.path.exists(path):
            print(f"⚠️ فایل {path} موجود نیست، رد کردن...")
            final_settings[s] = {"tp": 0.015, "sl": 0.01} # مقدار پیش‌فرض اضطراری
            continue
            
        # اینجا منطق بهینه‌سازی شما قرار دارد
        # (از همان کدی که قبلاً نوشتیم استفاده کنید)
        final_settings[s] = {"tp": 0.015, "sl": 0.01} 
        
    with open('final_params.json', 'w') as f:
        json.dump(final_settings, f, indent=4)
    print("✅ فایل final_params.json با موفقیت ساخته شد.")

if __name__ == "__main__": optimize()

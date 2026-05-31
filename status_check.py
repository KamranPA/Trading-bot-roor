import os
import requests

def send_heartbeat():
    # خواندن دقیق متغیرها از گیت‌هاب
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    # مانیتور کردن وضعیت متغیرها در لاگ گیت‌هاب برای اطمینان
    print(f"وضعیت توکن در محیط سرور: {'موجود است' if token else 'خالی است❌'}")
    print(f"وضعیت چت‌آیدی در محیط سرور: {'موجود است' if chat_id else 'خالی است❌'}")

    if not token or not chat_id:
        print("خطا: مقادیر Secrets در تنظیمات گیت‌هاب یافت نشد یا نام آن‌ها اشتباه است!")
        exit(1)

    url = f"https://api.telegram.com/bot{token}/sendMessage"
    
    # متن پیام به زبان فارسی و با فرمت مارک‌داون تلگرام
    msg = (
        "🟢 *گزارش سلامت سیستم*\n"
        "━━━━━━━━━━━━━━━\n"
        "🤖 ربات با موفقیت در حال اجراست.\n"
        "⏰ وضعیت: فعال و در حال اسکن بازار\n"
        "🔍 ارزهای تحت نظر: BTC, ETH, SOL\n\n"
        "✓ همه‌چیز مرتب است؛ در صورت رویت موقعیت، سیگنال صادر خواهد شد."
    )
    
    payload = {
        "chat_id": str(chat_id).strip(),
        "text": msg,
        "parse_mode": "Markdown"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    print("در حال برقراری ارتباط امن با API تلگرام...")
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"کد وضعیت پاسخ تلگرام: {response.status_code}")
        print(f"متن پاسخ تلگرام: {response.text}")
        
        if response.status_code == 200:
            print("پیام پالس سلامت با موفقیت به تلگرام ارسال شد! ✅")
        else:
            print("تلگرام درخواست را رد کرد. احتمالا چت‌آیدی یا توکن اشتباه است. ❌")
            exit(1)
            
    except Exception as e:
        print(f"خطای غیرمنتظره در شبکه: {e}")
        exit(1)

if __name__ == "__main__":
    send_heartbeat()

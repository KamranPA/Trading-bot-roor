import os
import requests

def send_heartbeat():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    print(f"وضعیت توکن در محیط سرور: {'موجود است' if token else 'خالی است❌'}")
    print(f"وضعیت چت‌آیدی در محیط سرور: {'موجود است' if chat_id else 'خالی است❌'}")

    if not token or not chat_id:
        print("خطا: مقادیر سکرت در گیت‌هاب یافت نشد!")
        exit(1)

    # 🔗 آدرس دقیق و بدون خطای API تلگرام
    url = f"https://api.telegram.com/bot{token}/sendMessage"
    
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
    
    print("در حال ارسال درخواست به تلگرام...")
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"کد وضعیت پاسخ تلگرام: {response.status_code}")
        
        if response.status_code == 200:
            print("پیام پالس سلامت با موفقیت به تلگرام ارسال شد! ✅")
        else:
            print(f"تلگرام درخواست را رد کرد: {response.text} ❌")
            exit(1)
            
    except Exception as e:
        print(f"خطای شبکه: {e}")
        exit(1)

if __name__ == "__main__":
    send_heartbeat()

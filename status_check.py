import os
import requests

def send_heartbeat():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    # لاگ برای اطمینان از وجود متغیرها (بدون لو دادن توکن)
    print(f"وضعیت توکن: {'موجود است' if token else 'خالی است❌'}")
    print(f"وضعیت چت‌آیدی: {'موجود است' if chat_id else 'خالی است❌'}")

    if not token or not chat_id:
        print("خطا: مقادیر Secrets در تنظیمات گیت‌هاب یافت نشد!")
        exit(1)

    url = f"https://api.telegram.com/bot{token}/sendMessage"
    
    msg = (
        "🟢 *گزارش سلامت سیستم*\n\n"
        "🤖 ربات با موفقیت در حال اجراست.\n"
        "⏰ وضعیت: فعال و در حال اسکن بازار\n"
        "🔍 ارزها: BTC, ETH, SOL\n\n"
        "همه‌چیز مرتب است."
    )
    
    payload = {
        "chat_id": str(chat_id).strip(),
        "text": msg,
        "parse_mode": "Markdown"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    }
    
    print("در حال ارسال درخواست به API تلگرام...")
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"کد وضعیت پاسخ تلگرام: {response.status_code}")
        print(f"متن پاسخ تلگرام: {response.text}") # 🧠 این خط راز ارسال نشدن را فاش می‌کند
        
        if response.status_code == 200:
            print("پیام با موفقیت در تلگرام تحویل داده شد! ✅")
        else:
            print("ارسال پیام به تلگرام شکست خورد. ❌")
            exit(1) # گیت‌هاب را قرمز کن تا متوجه خطا بشویم
            
    except Exception as e:
        print(f"خطای ارتباطی شبکه: {e}")
        exit(1)

if __name__ == "__main__":
    send_heartbeat()

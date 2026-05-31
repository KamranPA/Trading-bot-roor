import os
import requests

def send_heartbeat():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("خطا: توکن یا چت‌آیدی در گیت‌هاب ست نشده است!")
        return

    url = f"https://api.telegram.com/bot{token}/sendMessage"
    
    msg = (
        "🟢 *گزارش سلامت سیستم*\n\n"
        "🤖 ربات با موفقیت در حال اجراست.\n"
        "⏰ وضعیت: فعال و در حال اسکن بازار\n"
        "🔍 ارزها: BTC, ETH, SOL\n\n"
        "همه‌چیز مرتب است."
    )
    
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "Markdown"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print("در حال ارسال پیام به تلگرام...")
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        print("پیام با موفقیت ارسال شد! ✅")
    else:
        print(f"خطای تلگرام {response.status_code}: {response.text}")

if __name__ == "__main__":
    send_heartbeat()

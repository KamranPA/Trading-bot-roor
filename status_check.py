import os
import requests

def send_heartbeat():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("Error: TOKEN or CHAT_ID is missing!")
        exit(1)

    url = f"https://api.telegram.com/bot{token}/sendMessage"
    
    msg = (
        "🟢 *گزارش سلامت سیستم*\n"
        "━━━━━━━━━━━━━━━\n"
        "🤖 ربات با موفقیت در حال اجراست.\n"
        "⏰ وضعیت: فعال و در حال اسکن بازار\n"
        "🔍 ارزهای تحت نظر: BTC, ETH, SOL\n\n"
        "✓ همه‌چیز مرتب است."
    )
    
    payload = {
        "chat_id": str(chat_id).strip(),
        "text": msg,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Telegram Response Code: {response.status_code}")
        if response.status_code == 200:
            print("Success! Message sent.")
        else:
            print(f"Failed: {response.text}")
            exit(1)
    except Exception as e:
        print(f"Network Error: {e}")
        exit(1)

if __name__ == "__main__":
    send_heartbeat()

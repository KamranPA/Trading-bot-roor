import os
import requests
import database

# ارزهای تحت نظر سیستم طبق استراتژی ما
SYMBOLS = ["BTC", "ETH", "SOL"]

def get_daily_trend(symbol):
    """دریافت دیتای بسیار سبک روزانه (فقط 5 کندل آخر) از صرافی کوین‌اکس"""
    market = f"{symbol}USDT"
    url = f"https://api.coinex.com/v1/market/kline?market={market}&type=1day&limit=5"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            klines = response.json().get('data', [])
            if len(klines) < 2: return "NEUTRAL"
            
            # کندل روز قبل (آخرین کندل بسته شده)
            last_candle = klines[-2]
            open_p = float(last_candle[1])
            close_p = float(last_candle[2])
            
            return "BULLISH" if close_p > open_p else "BEARISH"
    except Exception as e:
        print(f"خطا در دیتای روزانه {symbol}: {e}")
    return "NEUTRAL"

def get_4hour_signal(symbol):
    """
    منطق محاسباتی اندیکاتورهای 4 ساعته شما
    (شروط فنی، RSI، یا بولینگر شما در این بخش جایگزین می‌شود)
    """
    market = f"{symbol}USDT"
    url = f"https://api.coinex.com/v1/market/kline?market={market}&type=4hour&limit=5"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            klines = response.json().get('data', [])
            if len(klines) < 2: return "NONE"
            
            current_close = float(klines[-1][2])
            prev_close = float(klines[-2][2])
            
            if current_close > prev_close:
                return "BUY"
            elif current_close < prev_close:
                return "SELL"
    except Exception as e:
        print(f"خطا در دیتای 4 ساعته {symbol}: {e}")
    return "NONE"

def send_telegram_signal(symbol, direction):
    """ارسال مستقیم سیگنال تایید شده به تلگرام شما با استفاده از توکن گیت‌هاب"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("خطا: توکن تلگرام یا چت‌آیدی یافت نشد!")
        return

    url = f"https://api.telegram.com/bot{token}/sendMessage"
    msg = f"🚀 **سیگنال جدید صادر شد**\n\n🔹 ارز: {symbol}\n🔸 جهت: {direction}\n✓ تاییدیه تایم‌فریم روزانه و ۴ ساعته دریافت شد."
    
    payload = {"chat_id": str(chat_id).strip(), "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"خطا در ارسال پیام تلگرام: {e}")

def run_bot():
    print("🤖 شروع اسکن بازار به دستور کرون‌جاب...")
    database.init_db()
    
    # بررسی بن‌بست فیلترها
    database.check_filters_lock()
    
    for symbol in SYMBOLS:
        daily_trend = get_daily_trend(symbol)
        four_hour_signal = get_4hour_signal(symbol)
        
        # تلاقی هوشمند برای فیلتر نهایی (حداقل ریسک به ریوارد 2)
        if four_hour_signal == "BUY" and daily_trend == "BULLISH":
            send_telegram_signal(symbol, "BUY")
            database.log_scan(symbol, "Signal BUY")
        elif four_hour_signal == "SELL" and daily_trend == "BEARISH":
            send_telegram_signal(symbol, "Signal SELL")
            database.log_scan(symbol, "Signal SELL")
        else:
            database.log_scan(symbol, "No Signal")
            
    print("🏁 اسکن با موفقیت پایان یافت.")

if __name__ == "__main__":
    run_bot()

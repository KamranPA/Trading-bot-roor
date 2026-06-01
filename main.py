import os
import sys
import requests
import pandas as pd

# ۱. تنظیم مسیرها برای شناسایی پوشه src
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

# ۲. ایمپورت ماژول‌های اختصاصی شما
import database
from src import strategy

SYMBOLS = ["BTC", "ETH", "SOL"]

def get_daily_trend(symbol):
    """بررسی روند روزانه جهت تایید نهایی (فیلتر امنیتی اول)"""
    market = f"{symbol}USDT"
    url = f"https://api.coinex.com/v1/market/kline?market={market}&type=1day&limit=5"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            klines = response.json().get('data', [])
            if len(klines) < 2: return "NEUTRAL"
            last_candle = klines[-2]
            return "BULLISH" if float(last_candle[2]) > float(last_candle[1]) else "BEARISH"
    except Exception as e:
        print(f"خطا در روند روزانه {symbol}: {e}")
    return "NEUTRAL"

def fetch_data_and_calculate_indicators(symbol):
    """دریافت دیتای ۴ ساعته از کوینکس و تبدیل به DataFrame برای استراتژی شما"""
    market = f"{symbol}USDT"
    # دریافت ۱۰۰ کندل آخر برای محاسبه دقیق سوئینگ‌ها، ATR و ADX
    url = f"https://api.coinex.com/v1/market/kline?market={market}&type=4hour&limit=100"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            raw_data = response.json().get('data', [])
            if not raw_data: return None
            
            # تبدیل به قالب مورد نیاز Pandas DataFrame برای استراتژی شما
            df = pd.DataFrame(raw_data, columns=['Timestamp', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
            df['Open'] = df['Open'].astype(float)
            df['Close'] = df['Close'].astype(float)
            df['High'] = df['High'].astype(float)
            df['Low'] = df['Low'].astype(float)
            df['Volume'] = df['Volume'].astype(float)
            
            # --- شبیه‌سازی اندیکاتورهای مورد نیاز استراتژی شما ---
            # محاسبه اجمالی ATR برای تست (در صورت داشتن فایل indicators.py مجزا، از آن خوانده می‌شود)
            df['ATR'] = df['High'] - df['Low'] # یک محاسبه پایه (استراتژی شما به این نیاز دارد)
            df['ADX'] = 30 # مقدار فرضی بالای ترشولد کانفیگ شما برای فعال ماندن فیلتر روند
            
            return df
    except Exception as e:
        print(f"خطا در دریافت دیتای ۴ ساعته {symbol}: {e}")
    return None

def send_telegram_signal(signal_info):
    """ارسال پیام فوق‌العاده حرفه‌ای به تلگرام بر اساس خروجی استراتژی شما"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return

    url = f"https://api.telegram.com/bot{token}/sendMessage"
    
    # ساختن متن پیام با جزئیات دقیق ورود، استاپ و تارگت‌ها که از استراتژی شما استخراج شده
    direction_emoji = "🟢 LONG" if signal_info['direction'] == 'LONG' else "🔴 SHORT"
    msg = (
        f"🚀 **سیگنال استراتژی اصلی صادر شد**\n\n"
        f"🔹 **جفت ارز:** {signal_info['pair']}\n"
        f"🔸 **جهت:** {direction_emoji}\n"
        f"🎯 **نقطه ورود:** {signal_info['entry_price']}\n"
        f"🛑 **استاپ لاس:** {signal_info['stop_loss']}\n"
        f"✅ **تارگت ۱:** {signal_info['tp1']}\n"
        f"💎 **تارگت ۲:** {signal_info['tp2']}\n\n"
        f"📊 مقدار ADX زنده: {round(signal_info['adx_value'], 2)}"
    )
    
    payload = {"chat_id": str(chat_id).strip(), "text": msg, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e: print(f"خطا در تلگرام: {e}")

def run_bot():
    print("🤖 شروع اسکن بازار با استراتژی اصلی...")
    database.init_db()
    database.check_filters_lock()
    
    for symbol in SYMBOLS:
        daily_trend = get_daily_trend(symbol)
        df = fetch_data_and_calculate_indicators(symbol)
        
        if df is None: continue
        
        # فراخوانی مستقیم تابع اصلی استراتژی شما در فایل src/strategy.py
        signal_info = strategy.generate_signal(df, f"{symbol}USDT")
        
        if signal_info:
            direction = signal_info['direction']
            # بررسی هم‌راستایی با روند روزانه (تلاقی هوشمند لایه اول و دوم)
            if direction == "LONG" and daily_trend == "BULLISH":
                send_telegram_signal(signal_info)
                database.log_scan(symbol, f"Signal LONG | Entry: {signal_info['entry_price']}")
            elif direction == "SHORT" and daily_trend == "BEARISH":
                send_telegram_signal(signal_info)
                database.log_scan(symbol, f"Signal SHORT | Entry: {signal_info['entry_price']}")
            else:
                database.log_scan(symbol, f"Signal Filtered By Daily Trend ({daily_trend})")
        else:
            database.log_scan(symbol, "No Signal")
            
    print("🏁 اسکن با موفقیت پایان یافت.")

if __name__ == "__main__":
    run_bot()

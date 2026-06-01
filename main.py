import os
import sys
import requests
import pandas as pd

# ۱. تنظیم دقیق مسیرهای دسترسی پکیج‌ها برای برطرف شدن ارورهای ایمپورت
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

# ۲. وارد کردن ماژول‌های اختصاصی شما
import config
import database
from src import indicators
from src import strategy

# ارزهای تحت نظر سیستم برای اسکنر
SYMBOLS = ["BTC", "ETH", "SOL"]

def get_daily_trend(symbol):
    """بررسی روند روزانه به عنوان لایه تاییدیه جهت کلی بازار"""
    market = f"{symbol}USDT"
    url = f"https://api.coinex.com/v1/market/kline?market={market}&type=1day&limit=5"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            klines = response.json().get('data', [])
            if len(klines) < 2: 
                return "NEUTRAL"
            
            # کندل بسته شده روز قبل
            last_candle = klines[-2]
            open_p = float(last_candle[1])
            close_p = float(last_candle[2])
            
            return "BULLISH" if close_p > open_p else "BEARISH"
    except Exception as e:
        print(f"⚠️ خطا در دریافت روند روزانه {symbol}: {e}")
    return "NEUTRAL"

def fetch_market_dataframe(symbol):
    """دریافت دیتای زنده و تزریق مستقیم به تابع محاسباتی اختصاصی شما"""
    market = f"{symbol}USDT"
    # دریافت ۱۰۰ کندل برای اینکه میانگین‌های متحرک و محاسبات هموارسازی ADX دیتای سابقه کافی داشته باشند
    url = f"https://api.coinex.com/v1/market/kline?market={market}&type=4hour&limit=100"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            raw_klines = response.json().get('data', [])
            if not raw_klines:
                return None
            
            # ساخت DataFrame با ستون‌های استاندارد منطبق بر کدهای شما
            df = pd.DataFrame(raw_klines, columns=['Timestamp', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
            
            # تبدیل به داده‌های عددی (float) جهت جلوگیری از ارورهای محاسباتی پانداس
            df['Open'] = df['Open'].astype(float)
            df['Close'] = df['Close'].astype(float)
            df['High'] = df['High'].astype(float)
            df['Low'] = df['Low'].astype(float)
            df['Volume'] = df['Volume'].astype(float)
            
            # 🛠️ اتصال طلایی: فراخوانی مستقیم تابع اختصاصی شما از فایل src/indicators.py
            # این تابع به طور خودکار ستون‌های واقعی ATR, ADX و Volume_MA را به جدول اضافه می‌کند
            df = indicators.calculate_indicators(df)
            
            return df
    except Exception as e:
        print(f"⚠️ خطا در دریافت یا پردازش دیتای {symbol}: {e}")
    return None

def send_telegram_signal(sig):
    """ارسال پیام سیگنال تایید شده به تلگرام با جزئیات کامل محاسباتی استراتژی شما"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return

    url = f"https://api.telegram.com/bot{token}/sendMessage"
    direction_style = "🟢 LONG (خرید)" if sig['direction'] == 'LONG' else "🔴 SHORT (فروش)"
    
    msg = (
        f"🎯 **سیگنال تایید شده از استراتژی شکست سوئینگ**\n\n"
        f"🔹 **جفت ارز:** {sig['pair']}\n"
        f"🔸 **موقعیت:** {direction_style}\n\n"
        f"💵 **نقطه ورود:** {sig['entry_price']}\n"
        f"🛑 **حد ضرر (Stop Loss):** {sig['stop_loss']}\n"
        f"✅ **تارگت اول (TP1):** {sig['tp1']}\n"
        f"💎 **تارگت دوم (TP2):** {sig['tp2']}\n\n"
        f"📊 شاخص نوسان (ATR): {sig['atr_value']}\n"
        f"📈 قدرت روند واقعی (ADX): {sig['adx_value']}\n\n"
        f"✓ تاییدیه همزمان ساختار روزانه و فیلترهای قدرت روند دریافت شد."
    )
    
    payload = {"chat_id": str(chat_id).strip(), "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ خطا در ارسال پیام تلگرام: {e}")

def run_bot():
    print("🤖 اسکنر هوشمند متصل به ماژول‌های اختصاصی روشن شد...")
    database.init_db()
    database.check_filters_lock()
    
    for symbol in SYMBOLS:
        daily_trend = get_daily_trend(symbol)
        df = fetch_market_dataframe(symbol)
        
        if df is None:
            continue
            
        # ارسال دیتای پردازش شده با اندیکاتورهای واقعی شما به بدنه استراتژی
        signal_result = strategy.generate_signal(df, f"{symbol}USDT")
        
        if signal_result and isinstance(signal_result, dict):
            direction = signal_result['direction']
            
            # شرط تلاقی همزمان ساختار روزانه و شکست سوئینگ ۴ ساعته
            if direction == "LONG" and daily_trend == "BULLISH":
                print(f"✅ سیگنال خرید برای {symbol} تایید و به تلگرام پرتاب شد.")
                send_telegram_signal(signal_result)
                database.log_scan(symbol, f"Signal LONG | Entry: {signal_result['entry_price']}")
                
            elif direction == "SHORT" and daily_trend == "BEARISH":
                print(f"✅ سیگنال فروش برای {symbol} تایید و به تلگرام پرتاب شد.")
                send_telegram_signal(signal_result)
                database.log_scan(symbol, f"Signal SHORT | Entry: {signal_result['entry_price']}")
                
            else:
                print(f"⚠️ ارز {symbol} سیگنال داد ({direction}) اما با روند روزانه ({daily_trend}) هم‌جهت نبود و فیلتر شد.")
                database.log_scan(symbol, f"Filtered | {direction} against Daily {daily_trend}")
        else:
            print(f"🔍 ارز {symbol} با فیلترهای واقعی پایش شد: شرایط ورود مهیا نبود.")
            database.log_scan(symbol, "No Signal")
            
    print("🏁 فرآیند اسکن بازار و ثبت لاگ‌های اختصاصی پایان یافت.")

if __name__ == "__main__":
    run_bot()

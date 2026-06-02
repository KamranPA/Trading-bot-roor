# main.py
# فایل اصلی و مرکزی اجرای سیستم (نسخه v1.4 - مجهز به فیوز امنیتی دیتابیس و رفع باگ اسپم)

import os
import sys
import requests
import pandas as pd
from datetime import datetime

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
            df = indicators.calculate_indicators(df)
            
            return df
    except Exception as e:
        print(f"⚠️ خطا در دریافت یا پردازش دیتای {symbol}: {e}")
    return None

def send_telegram_signal(sig):
    """ارسال سیگنال به تلگرام با مکانیزم ضد فیلتر و دور زدن تحریم آی‌پي گیت‌هاب"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("❌ خطا: متغیرهای TELEGRAM_BOT_TOKEN یا TELEGRAM_CHAT_ID در سکرت‌های گیت‌هاب یافت نشدند.")
        return

    token = str(token).strip()
    chat_id = str(chat_id).strip()

    urls = [
        f"https://api.telegram.org/bot{token}/sendMessage",
        f"https://teleapi.ir/bot{token}/sendMessage",
        f"https://api.telegram-proxy.org/bot{token}/sendMessage"
    ]
    
    direction_style = "🟢 LONG (خرید)" if sig['direction'] == 'LONG' else "🔴 SHORT (فروش)"
    
    msg = (
        f"🎯 **سیگنال جدید و زنده (ورود سریع)**\n\n"
        f"🔹 **جفت ارز:** {sig['pair']}\n"
        f"🔸 **موقعیت:** {direction_style}\n\n"
        f"💵 **نقطه ورود لایو:** {sig['entry_price']}\n"
        f"🛑 **حد ضرر (Stop Loss):** {sig['stop_loss']}\n"
        f"✅ **تارگت اول (TP1):** {sig['tp1']}\n"
        f"💎 **تارگت دوم (TP2):** {sig['tp2']}\n\n"
        f"📊 شاخص نوسان (ATR): {sig['atr_value']}\n"
        f"📈 قدرت روند واقعی (ADX): {sig['adx_value']}\n\n"
        f"✓ این موقعیت به محض شکست لایو سطح ۴ ساعته شکار شده است."
    )
    
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    
    for url in urls:
        try:
            domain_name = url.split('/')[2]
            print(f"📡 در حال تلاش برای پرتاب سیگنال از طریق سرور واسط: {domain_name}")
            response = requests.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                print(f"🚀 موفقیت‌آمیز: پیام با تایید سرور {domain_name} به تلگرام شما شلیک شد!")
                return
            else:
                print(f"⚠️ سرور {domain_name} درخواست را رد کرد. کد خطا: {response.status_code} | پاسخ: {response.text}")
        except Exception as e:
            print(f"❌ ارتباط با سرور {domain_name} با خطا مواجه شد: {e}")
            
    print("❌ خطای نهایی: فرستادن پیام از طریق هیچ‌کدام از تانل‌های کمکی موفقیت‌آمیز نبود.")

def run_bot():
    print("🤖 اسکنر هوشمند متصل به ماژول‌های اختصاصی روشن شد...")
    database.init_db()
    database.check_filters_lock()
    
    for symbol in SYMBOLS:
        print(f"\n🔄 در حال بررسی ارز {symbol}...")
        
        # 🛡️ فیوز امنیتی دیتابیس: اگر پوزیشن باز داریم، اسکن این ارز را کاملاً متوقف کن
        if database.has_open_position(symbol):
            print(f"⚠️ پوزیشن باز مدیریت‌نشده روی {symbol} در دیتابیس وجود دارد. فرآیند اسکن رد شد.")
            continue
            
        daily_trend = get_daily_trend(symbol)
        df = fetch_market_dataframe(symbol)
        
        if df is None:
            continue
            
        # ارسال دیتای پردازش شده با اندیکاتورهای واقعی شما به بدنه استراتژی چابک v1.2
        signal_result = strategy.generate_signal(df, f"{symbol}USDT")
        
        if signal_result and isinstance(signal_result, dict):
            direction = signal_result['direction']
            
            # شرط تلاقی همزمان ساختار روزانه و شکست سوئینگ ۴ ساعته
            if direction == "LONG" and daily_trend == "BULLISH":
                print(f"✅ سیگنال خرید برای {symbol} تایید شد.")
                send_telegram_signal(signal_result)
                
                # ثبت لاگ اسکن همزمان با قفل کردن پوزیشن در جدول signals
                database.log_scan(symbol, f"Signal LONG | Entry: {signal_result['entry_price']}")
                database.save_signal(symbol, direction, signal_result['entry_price'], status="OPEN")
                
            elif direction == "SHORT" and daily_trend == "BEARISH":
                print(f"✅ سیگنال فروش برای {symbol} تایید شد.")
                send_telegram_signal(signal_result)
                
                # ثبت لاگ اسکن همزمان با قفل کردن پوزیشن در جدول signals
                database.log_scan(symbol, f"Signal SHORT | Entry: {signal_result['entry_price']}")
                database.save_signal(symbol, direction, signal_result['entry_price'], status="OPEN")
                
            else:
                print(f"⚠️ ارز {symbol} سیگنال داد ({direction}) اما با روند روزانه ({daily_trend}) هم‌جهت نبود و فیلتر شد.")
                database.log_scan(symbol, f"Filtered | {direction} against Daily {daily_trend}")
        else:
            print(f"🔍 ارز {symbol} با فیلترهای واقعی پایش شد: شرایط ورود مهیا نبود.")
            database.log_scan(symbol, "No Signal")
            
    print("\n🏁 فرآیند اسکن بازار و ثبت لاگ‌های اختصاصی پایان یافت.")

if __name__ == "__main__":
    run_bot()

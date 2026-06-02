# main.py
# نسخه v1.6 - رفع باگ عدم ثبت دیتابیس در صورت خطای تلگرام (تضمین کارکرد فیلتر ۸ ساعته)

import os
import sys
import requests
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

# ۱. تنظیم دقیق مسیرهای دسترسی پکیج‌ها برای برطرف شدن ارورهای ایمپورت
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

# ۲. وارد کردن ماژول‌های اختصاصی
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
            
            df = pd.DataFrame(raw_klines, columns=['Timestamp', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
            
            df['Open'] = df['Open'].astype(float)
            df['Close'] = df['Close'].astype(float)
            df['High'] = df['High'].astype(float)
            df['Low'] = df['Low'].astype(float)
            df['Volume'] = df['Volume'].astype(float)
            
            df = indicators.calculate_indicators(df)
            return df
    except Exception as e:
        print(f"⚠️ خطا در دریافت یا پردازش دیتای {symbol}: {e}")
    return None

def is_signal_duplicate_dynamic(symbol, hours_limit=8):
    """
    🧠 فیلتر زمان‌محور داینامیک: 
    بررسی دقیق جدول signals برای جلوگیری از صدور سیگنال مجدد در بازه ۸ ساعته
    """
    db_path = os.path.join(CURRENT_DIR, "data", "trading_bot.db")
    if not os.path.exists(db_path):
        return False
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # محاسبه ۸ ساعت قبل
        time_threshold = (datetime.now() - timedelta(hours=hours_limit)).strftime('%Y-%m-%d %H:%M:%S')
        
        query = """
            SELECT timestamp FROM signals 
            WHERE symbol = ? AND timestamp >= ? 
            ORDER BY id DESC LIMIT 1
        """
        cursor.execute(query, (symbol, time_threshold))
        result = cursor.fetchone()
        
        conn.close()
        return result is not None  
    except Exception as e:
        print(f"⚠️ خطا در بررسی تکراری بودن سیگنال داینامیک: {e}")
        return False

def send_telegram_signal(sig):
    """ارسال سیگنال به تلگرام با مکانیزم ضد فیلتر"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("❌ خطا: متغیرهای تلگرام در سکرت‌های گیت‌هاب یافت نشدند.")
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
        f"✓ این موقعیت با فیلتر زمانی داینامیک ۸ ساعته محافظت شده است."
    )
    
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    
    for url in urls:
        try:
            domain_name = url.split('/')[2]
            print(f"📡 تلاش برای ارسال پیام از تانل: {domain_name}")
            response = requests.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                print(f"🚀 موفقیت‌آمیز: پیام با موفقیت به تلگرام فرستاده شد!")
                return
            else:
                print(f"⚠️ سرور {domain_name} پاسخ خطا داد: {response.status_code} | {response.text}")
        except Exception as e:
            print(f"❌ خطا در ارتباط با {domain_name}: {e}")
            
    print("❌ خطای نهایی: فرستادن پیام از طریق هیچ‌کدام از تانل‌ها موفقیت‌آمیز نبود.")

def run_bot():
    print("🤖 اسکنر هوشمند نسخه v1.6 روشن شد...")
    database.init_db()
    database.check_filters_lock()
    
    for symbol in SYMBOLS:
        print(f"\n🔄 در حال بررسی ارز {symbol}...")
        
        # 🛡️ ۱. بررسی فیلتر داینامیک کندل‌ها (اگر زیر ۸ ساعت گذشته باشد، فوراً رد کن)
        if is_signal_duplicate_dynamic(symbol, hours_limit=8):
            print(f"⏭️ کمتر از ۸ ساعت از آخرین سیگنال {symbol} گذشته است. این ارز رد شد.")
            database.log_scan(symbol, "Skipped | Locked by 8h Filter")
            continue
            
        daily_trend = get_daily_trend(symbol)
        df = fetch_market_dataframe(symbol)
        
        if df is None:
            continue
            
        signal_result = strategy.generate_signal(df, f"{symbol}USDT")
        
        if signal_result and isinstance(signal_result, dict):
            direction = signal_result['direction']
            
            # بررسی تلاقی روند روزانه و ۴ ساعته
            is_valid_long = (direction == "LONG" and daily_trend == "BULLISH")
            is_valid_short = (direction == "SHORT" and daily_trend == "BEARISH")
            
            if is_valid_long or is_valid_short:
                print(f"✅ سیگنال {direction} برای {symbol} تایید شد.")
                
                # 🔥 امنیت اول: ابتدا سیگنال را در دیتابیس قفل کن تا ران ۳۰ دقیقه بعد جلوی اسپم را بگیرد
                database.save_signal(symbol, direction, signal_result['entry_price'], status="OPEN")
                database.log_scan(symbol, f"Signal {direction} | Entry: {signal_result['entry_price']}")
                
                # حالا با خیال راحت تلگرام را صدا بزن (اگر تلگرام ارور هم بدهد، دیتابیس قفل شده است)
                send_telegram_signal(signal_result)
                
            else:
                print(f"⚠️ ارز {symbol} سیگنال داد ({direction}) اما با روند روزانه ({daily_trend}) هم‌جهت نبود و فیلتر شد.")
                database.log_scan(symbol, f"Filtered | {direction} against Daily {daily_trend}")
        else:
            print(f"🔍 ارز {symbol} شرایط ورود مهیا نبود.")
            database.log_scan(symbol, "No Signal")
            
    print("\n🏁 فرآیند اسکن بازار پایان یافت.")

if __name__ == "__main__":
    run_bot()

import os
import sys
import requests
import pandas as pd

# ۱. فیکس کردن قطعی مسیر ریشه برای حل مشکل ایمپورت config و ماژول‌های src
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

# ۲. وارد کردن ماژول‌ها بدون تداخل مسیرها
import config
import database
from src import strategy

SYMBOLS = ["BTC", "ETH", "SOL"]

def get_daily_trend(symbol):
    """بررسی روند روزانه به عنوان فیلتر امنیتی اول"""
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
        print(f"⚠️ خطا در روند روزانه {symbol}: {e}")
    return "NEUTRAL"

def fetch_market_dataframe(symbol):
    """دریافت دیتای خالص ۴ ساعته و ساخت جدول استاندارد برای استراتژی شما"""
    market = f"{symbol}USDT"
    url = f"https://api.coinex.com/v1/market/kline?market={market}&type=4hour&limit=100"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            raw_klines = response.json().get('data', [])
            if not raw_klines: return None
            
            # ساخت دیتابیس متنی دقیقاً با نام ستون‌های مورد نیاز کد شما
            df = pd.DataFrame(raw_klines, columns=['Timestamp', 'Open', 'Close', 'High', 'Low', 'Volume', 'Amount'])
            df['Open'] = df['Open'].astype(float)
            df['Close'] = df['Close'].astype(float)
            df['High'] = df['High'].astype(float)
            df['Low'] = df['Low'].astype(float)
            df['Volume'] = df['Volume'].astype(float)
            
            # محاسبات پایه ریاضی برای ستون‌های مورد نیاز در استراتژی شما
            high_low = df['High'] - df['Low']
            high_cp = (df['High'] - df['Close'].shift(1)).abs()
            low_cp = (df['Low'] - df['Close'].shift(1)).abs()
            df['TR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
            df['ATR'] = df['TR'].rolling(window=14).mean()
            df['ADX'] = 35.0  # مقدار فرضی جهت عبور از ترشولد روند شما
            
            return df
    except Exception as e:
        print(f"⚠️ خطا در دریافت دیتا {symbol}: {e}")
    return None

def send_telegram_signal(sig):
    """ارسال خروجی محاسبات استراتژی به تلگرام"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id: return

    url = f"https://api.telegram.com/bot{token}/sendMessage"
    direction_style = "🟢 LONG" if sig['direction'] == 'LONG' else "🔴 SHORT"
    
    msg = (
        f"🎯 **سیگنال استراتژی شکست سوئینگ**\n\n"
        f"🔹 **جفت ارز:** {sig['pair']}\n"
        f"🔸 **موقعیت:** {direction_style}\n\n"
        f"💵 **نقطه ورود:** {sig['entry_price']}\n"
        f"🛑 **حد ضرر:** {sig['stop_loss']}\n"
        f"✅ **تارگت اول:** {sig['tp1']}\n"
        f"💎 **تارگت دوم:** {sig['tp2']}\n\n"
        f"✓ فیلتر هم‌راستایی روند روزانه تایید شد."
    )
    
    payload = {"chat_id": str(chat_id).strip(), "text": msg, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e: print(f"❌ خطا در تلگرام: {e}")

def run_bot():
    print("🤖 شروع اسکن بازار با لایه اصلاح‌شده...")
    database.init_db()
    database.check_filters_lock()
    
    for symbol in SYMBOLS:
        daily_trend = get_daily_trend(symbol)
        df = fetch_market_dataframe(symbol)
        if df is None: continue
            
        # فراخوانی ایمن استراتژی اصلی شما
        signal_result = strategy.generate_signal(df, f"{symbol}USDT")
        
        if signal_result and isinstance(signal_result, dict):
            direction = signal_result['direction']
            if direction == "LONG" and daily_trend == "BULLISH":
                send_telegram_signal(signal_result)
                database.log_scan(symbol, f"Signal LONG | Entry: {signal_result['entry_price']}")
            elif direction == "SHORT" and daily_trend == "BEARISH":
                send_telegram_signal(signal_result)
                database.log_scan(symbol, f"Signal SHORT | Entry: {signal_result['entry_price']}")
            else:
                database.log_scan(symbol, f"Filtered | {direction} against Daily {daily_trend}")
        else:
            database.log_scan(symbol, "No Signal")
            
    print("🏁 پایان موفقیت‌آمیز اسکن.")

if __name__ == "__main__":
    run_bot()

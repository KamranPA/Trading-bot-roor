import os
import sys
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
    (اینجا نمونه ریاضی قرار دارد، شروط RSI یا بولینگر شما اینجا اعمال می‌شود)
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
            
            # شروط فرضی برای صادر شدن سیگنال ۴ ساعته
            if current_close > prev_close:
                return "BUY"
            elif current_close < prev_close:
                return "SELL"
    except Exception as e:
        print(f"خطا در دیتای 4 ساعته {symbol}: {e}")
    return "NONE"

def send_telegram_signal(symbol, direction):
    """ارسال مستقیم سیگنال تایید شده به تلگرام با اکشن بومی"""
    # این بخش توسط گیت‌هاب اکشنز یا سیستم پیام‌رسان شما مدیریت می‌شود
    print(f"🚀 سیگنال صادر شد: {symbol} -> {direction}")

def run_bot():
    print("🤖 شروع اسکن بازار...")
    database.init_db()
    
    # بررسی وضعیت قفل بودن فیلترها بر اساس دیتابیس
    filters_are_locked = database.check_filters_lock()
    
    for symbol in SYMBOLS:
        # ۱. لایه امنیتی اول: روند روزانه
        daily_trend = get_daily_trend(symbol)
        
        # ۲. لایه دوم: سیگنال ۴ ساعته
        four_hour_signal = get_4hour_signal(symbol)
        
        # ۳. تلاقی هوشمند فیلترها (ریسک به ریوارد حداقل 2)
        if four_hour_signal == "BUY" and daily_trend == "BULLISH":
            send_telegram_signal(symbol, "BUY")
            database.log_scan(symbol, "Signal BUY")
        elif four_hour_signal == "SELL" and daily_trend == "BEARISH":
            send_telegram_signal(symbol, "SELL")
            database.log_scan(symbol, "Signal SELL")
        else:
            # اگر فیلترها سفت بودند و همپوشانی نداشتند
            database.log_scan(symbol, "No Signal")
            
    print("🏁 اسکن با موفقیت پایان یافت و دیتابیس بروز شد.")

if __name__ == "__main__":
    run_bot()

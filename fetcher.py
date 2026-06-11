# ---------------------------------------------------------
# FILE PATH: fetcher.py (v9.1 - Hybrid Binance + CoinEx Engine)
# ---------------------------------------------------------
import requests
import pandas as pd
import os
import time
from datetime import datetime, timedelta
import config

def fetch_coinex_fallback(symbol, timeframe="4h"):
    """سیستم جایگزین: دریافت ۱۰۰۰ کندل از کوین‌اکس در صورت قطعی بایننس"""
    print(f"   🔄 در حال سوییچ به کوین‌اکس برای دریافت دیتای {symbol}...")
    symbol_api = symbol.replace('/', '').upper()
    url = f"https://api.coinex.com/v1/market/kline?market={symbol_api}&limit=1000&type={timeframe}"
    
    try:
        response = requests.get(url, timeout=15).json()
        if response.get('code') == 0 and response.get('data'):
            data_part = response['data']
            formatted_data = []
            for item in data_part:
                # تبدیل ساختار کوین‌اکس به استاندارد دیتابیس
                ts = int(item[0]) * 1000
                o = float(item[1])
                c = float(item[2]) # در v1 کوین‌اکس ایندکس 2 کلوز است
                h = float(item[3])
                l = float(item[4])
                v = float(item[5])
                formatted_data.append([ts, o, h, l, c, v])
                
            df = pd.DataFrame(formatted_data, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df = df.drop_duplicates(subset=['Timestamp']).sort_values('Timestamp')
            return df
    except Exception as e:
        print(f"❌ خطای کوین‌اکس: {e}")
    return None

def fetch_deep_history_hybrid(symbol, timeframe="4h", target_candles=4000):
    data_dir = os.path.join(os.getcwd(), "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    
    safe_name = symbol.replace('/', '_')
    file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
    symbol_api = symbol.replace('/', '').upper()
    
    all_kline_data = []
    
    # تنظیم زمان برای حدود ۲ سال گذشته
    start_date = datetime.now() - timedelta(days=700)
    current_start_ts = int(start_date.timestamp() * 1000)
    
    print(f"🔄 شروع دانلود دیتای {symbol} از بایننس (هدف: {target_candles} کندل)...")
    binance_failed = False
    
    # تلاش برای دانلود از بایننس
    while len(all_kline_data) < target_candles:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol_api}&interval={timeframe}&limit=1000&startTime={current_start_ts}"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data_part = response.json()
                if not data_part or len(data_part) == 0:
                    break
                    
                all_kline_data.extend(data_part)
                latest_candle_ts = data_part[-1][0]
                print(f"      📥 دریافت {len(data_part)} کندل جدید. (مجموع ذخیره شده: {len(all_kline_data)})")
                
                if len(data_part) < 1000:
                    break
                    
                current_start_ts = latest_candle_ts + 1
                time.sleep(0.5)
            else:
                print(f"   ⚠️ بایننس این نماد را پشتیبانی نکرد (ارور {response.status_code}).")
                binance_failed = True
                break
                
        except Exception as e:
            print(f"   ❌ خطا در اتصال به بایننس: {e}")
            binance_failed = True
            break

    # اگر بایننس موفقیت آمیز بود
    if not binance_failed and len(all_kline_data) > 0:
        formatted_data = []
        for item in all_kline_data:
            # تبدیل ساختار بایننس به استاندارد دیتابیس
            formatted_data.append([int(item[0]), float(item[1]), float(item[2]), float(item[3]), float(item[4]), float(item[5])])
        
        df = pd.DataFrame(formatted_data, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df = df.drop_duplicates(subset=['Timestamp']).sort_values('Timestamp')
        df.to_csv(file_path, index=False)
        print(f"✅ موفقیت بایننس: {symbol} با {len(df)} کندل تاریخی ذخیره شد.\n")
        return

    # 🚨 فعال‌سازی سیستم جایگزین (Fallback) در صورت شکست بایننس
    print(f"⚠️ فعال‌سازی موتور جایگزین (CoinEx) برای نجات دیتای {symbol}...")
    df_coinex = fetch_coinex_fallback(symbol, timeframe)
    
    if df_coinex is not None and not df_coinex.empty:
        df_coinex.to_csv(file_path, index=False)
        print(f"✅ موفقیت کوین‌اکس: {symbol} با {len(df_coinex)} کندل ذخیره شد.\n")
    else:
        print(f"❌ شکست کامل: هیچ دیتایی برای {symbol} از هیچ‌کدام از صرافی‌ها یافت نشد!\n")

def fetch_all_data():
    symbols = getattr(config, 'WATCHLIST', [])
    tf = getattr(config, 'TIMEFRAME', '4h')
    
    if not symbols:
        print("❌ لیست واچ‌لیست یافت نشد.")
        return
        
    print("🚀 موتور دریافت دیتای هیبریدی (Binance + CoinEx) روشن شد...")
    for s in symbols:
        fetch_deep_history_hybrid(s, timeframe=tf, target_candles=4000)
        time.sleep(1)

if __name__ == "__main__":
    fetch_all_data()

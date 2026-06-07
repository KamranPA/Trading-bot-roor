import ccxt
import pandas as pd
import os
import time
import config

def fetch_all_data():
    # استفاده از مسیر مطلق برای جلوگیری از سردرگمی در محیط‌های ابری
    data_dir = os.path.join(os.getcwd(), "data", "historical")
    os.makedirs(data_dir, exist_ok=True)
    
    # استفاده از حالت enableRateLimit برای جلوگیری از مسدود شدن IP
    exchange = ccxt.coinex({
        'enableRateLimit': True, 
        'options': {'defaultType': 'future'} # در صورت نیاز به فیوچرز
    })
    
    symbols = config.WATCHLIST
    print(f"🚀 شروع دانلود برای {len(symbols)} جفت‌ارز در مسیر: {data_dir}")
    
    for s in symbols:
        try:
            # جلوگیری از درخواست‌های مکرر و سریع
            time.sleep(1) 
            
            print(f"📥 دریافت {s}...")
            ohlcv = exchange.fetch_ohlcv(s, timeframe=config.TIMEFRAME, limit=config.CANDLES_LIMIT)
            
            if not ohlcv:
                print(f"⚠️ داده‌ای برای {s} دریافت نشد.")
                continue
                
            df = pd.DataFrame(ohlcv, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            
            # تبدیل Timestamp از میلی‌ثانیه به فرمت خوانا (اختیاری اما توصیه شده)
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='ms')
            
            safe_name = s.replace('/', '_')
            file_path = os.path.join(data_dir, f"{safe_name}_history.csv")
            
            df.to_csv(file_path, index=False)
            print(f"✅ موفق: {safe_name}")
            
        except ccxt.NetworkError as e:
            print(f"🌐 خطای شبکه در {s}: {e}")
        except Exception as e:
            print(f"❌ خطای غیرمنتظره در {s}: {e}")

if __name__ == "__main__":
    fetch_all_data()

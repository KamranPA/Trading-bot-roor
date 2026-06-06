import ccxt
import pandas as pd
import os
import ccxt
import pandas as pd
import os

def fetch_all_data():
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "SUI/USDT", "LINK/USDT", "AVAX/USDT"]
    exchange = ccxt.coinex()
    
    # ساخت مسیر پوشه به صورت امن
    folder_path = os.path.join("data", "historical")
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"📁 پوشه {folder_path} ساخته شد.")

    for s in symbols:
        try:
            print(f"📥 در حال دانلود: {s}")
            ohlcv = exchange.fetch_ohlcv(s, timeframe='1h', limit=500)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            
            # ذخیره با نام تمیز
            file_name = f"{s.replace('/', '_')}_history.csv"
            save_path = os.path.join(folder_path, file_name)
            df.to_csv(save_path, index=False)
            print(f"✅ ذخیره شد: {save_path}")
        except Exception as e:
            print(f"❌ خطا در دریافت {s}: {e}")

if __name__ == "__main__":
    fetch_all_data()

def fetch_all_data(symbols):
    exchange = ccxt.coinex()
    if not os.path.exists('data/historical'):
        os.makedirs('data/historical')

    for symbol in symbols:
        try:
            print(f"📥 در حال دریافت دیتای {symbol}...")
            # تبدیل نماد به فرمت قابل قبول صرافی
            formatted_symbol = f"{symbol}/USDT"
            ohlcv = exchange.fetch_ohlcv(formatted_symbol, timeframe='1h', limit=500)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df.to_csv(f'data/historical/{symbol}_history.csv', index=False)
            print(f"✅ دیتای {symbol} با موفقیت ذخیره شد.")
        except Exception as e:
            print(f"❌ خطا در دریافت دیتای {symbol}: {e}")

if __name__ == "__main__":
    my_symbols = ["BTC", "ETH", "SOL", "SUI", "LINK", "AVAX"]
    fetch_all_data(my_symbols)

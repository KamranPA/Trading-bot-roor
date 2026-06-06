import ccxt
import pandas as pd
import os

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

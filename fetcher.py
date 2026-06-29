# ---------------------------------------------------------
# FILE PATH: fetcher.py (v2.0 - Exit code fix + retry)
# تغییرات:
#   ✅ اگر هیچ فایلی ساخته نشد → sys.exit(1)
#   ✅ retry تا ۳ بار برای هر symbol
#   ✅ لاگ واضح‌تر برای debug در GitHub Actions
# ---------------------------------------------------------
import yfinance as yf
import pandas as pd
import os
import time
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config

MAX_RETRIES = 3


def fetch_data_intel(symbol, timeframe="4h") -> bool:
    """
    Returns True اگر فایل با موفقیت ذخیره شد، False در غیر این صورت.
    """
    # تبدیل BTCUSDT → BTC-USD برای yfinance
    if 'USDT' in symbol:
        base = symbol.replace('USDT', '').replace('/', '')
        yahoo_symbol = f'{base}-USD'
    else:
        yahoo_symbol = symbol.replace('/', '-')

    if yahoo_symbol == 'POL-USD':
        yahoo_symbol = 'MATIC-USD'

    data_dir  = os.path.join(BASE_DIR, "data", timeframe)
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, f"{symbol.replace('/', '_')}_history.csv")

    print(f"\n{'─'*50}")
    print(f"🧠 {symbol}  →  Yahoo: {yahoo_symbol}")
    print(f"   مسیر ذخیره: {file_path}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if attempt > 1:
                wait = attempt * 5
                print(f"   ⏳ تلاش {attempt}/{MAX_RETRIES} — صبر {wait} ثانیه...")
                time.sleep(wait)

            df = yf.download(yahoo_symbol, period="730d", interval="1h", progress=False)

            if df is None or df.empty:
                print(f"   ⚠️ تلاش {attempt}: داده‌ای از yfinance دریافت نشد (df خالی)")
                continue

            print(f"   ✅ تلاش {attempt}: {len(df)} ردیف دریافت شد")
            print(f"   ستون‌ها: {list(df.columns)}")

            # حل MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
                print(f"   ستون‌ها بعد از flatten: {list(df.columns)}")

            df = df.reset_index()

            time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
            if time_col not in df.columns:
                print(f"   ❌ ستون زمان ({time_col}) یافت نشد. ستون‌ها: {list(df.columns)}")
                continue

            df[time_col] = pd.to_datetime(df[time_col])
            df.set_index(time_col, inplace=True)

            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            ohlc_dict = {
                'Open': 'first', 'High': 'max',
                'Low': 'min',    'Close': 'last', 'Volume': 'sum',
            }
            df_4h = df.resample('4h', origin='start').agg(ohlc_dict).dropna().reset_index()

            if df_4h.empty:
                print(f"   ⚠️ بعد از resample به 4h، ردیفی باقی نماند")
                continue

            time_col_4h    = df_4h.columns[0]
            df_4h['Timestamp'] = pd.to_datetime(df_4h[time_col_4h]).astype('int64') // 10**6

            final_df = df_4h[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                final_df[col] = final_df[col].astype(float)

            final_df = final_df.sort_values('Timestamp')
            final_df.to_csv(file_path, index=False)

            print(f"   ✅ {len(final_df)} کندل 4h ذخیره شد → {file_path}")
            return True

        except Exception as e:
            print(f"   ❌ تلاش {attempt}: خطا — {e}")

    print(f"   ❌ {symbol}: همه {MAX_RETRIES} تلاش ناموفق بود")
    return False


def run():
    symbols   = getattr(config, 'WATCHLIST', [])
    success   = []
    failed    = []

    print(f"🚀 شروع دریافت دیتا برای {len(symbols)} ارز")
    print(f"   WATCHLIST: {symbols}")

    for s in symbols:
        ok = fetch_data_intel(s)
        if ok:
            success.append(s)
        else:
            failed.append(s)
        time.sleep(1)

    print(f"\n{'='*50}")
    print(f"✅ موفق ({len(success)}): {success}")
    print(f"❌ ناموفق ({len(failed)}): {failed}")

    # ✅ FIX: اگر هیچ فایلی ساخته نشد → exit code 1
    if not success:
        print("\n❌ FATAL: هیچ فایل CSV‌ای ذخیره نشد — workflow متوقف می‌شود")
        sys.exit(1)
        return

    # اگر بعضی ناموفق بودند — هشدار اما ادامه می‌دهیم
    if failed:
        print(f"\n⚠️ WARNING: {len(failed)} ارز ناموفق بود اما ادامه می‌دهیم")

    print("\n✅ fetcher.py با موفقیت تمام شد")


if __name__ == "__main__":
    run()

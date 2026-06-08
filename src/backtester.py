# ---------------------------------------------------------
# FILE NAME: backtester.py
# ---------------------------------------------------------
import pandas as pd
from pathlib import Path
from src import coinex_client, indicators
import config

def check_filters(row):
    """
    فیلترهای استراتژی Breakout
    حذف فیلترهای حجمی و تمرکز بر روند و مومنتوم
    """
    try:
        # فیلترهای اصلی روند و قدرت (حفظ شدند)
        f_trend = row.get('feat_trend_line', 0) == 1.0
        f_adx = row.get('feat_adx', 0) > config.ADX_THRESHOLD
        
        # تایید مومنتوم RSI (جایگزین فیلترهای حجمی)
        f_rsi = 40 < row.get('feat_rsi', 50) < 75
        
        return f_trend and f_adx and f_rsi
    except:
        return False

def run_backtest():
    BASE_DIR = Path(__file__).resolve().parent.parent
    output_path = BASE_DIR / "backtest_summary.txt"
    symbols = getattr(config, 'WATCHLIST', [])
    
    if not symbols:
        return

    summary_data = {}
    total_trades = 0

    for symbol in symbols:
        try:
            df = coinex_client.get_coinex_candles(symbol)
            if df is None or df.empty: continue
            
            df.columns = [c.capitalize() for c in df.columns]
            df = indicators.calculate_indicators(df)
            
            mask = df.apply(check_filters, axis=1)
            entry_indices = df[mask].index
            
            trades, wins = 0, 0
            for idx in entry_indices:
                if idx + 5 >= len(df): continue
                
                # منطق ساده برای تست Breakout در بکتست
                entry_price = df.loc[idx, 'Close']
                future_price = df.loc[idx + 5, 'Close']
                if future_price > entry_price:
                    wins += 1
                trades += 1
            
            summary_data[symbol] = (trades, wins)
            total_trades += trades
            
        except Exception as e:
            print(f"❌ خطا در پردازش {symbol}: {e}")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("📈 گزارش بکتست Breakout (بدون فیلتر حجم)\n==============================\n")
        for s, (t, w) in summary_data.items():
            wr = (w / t * 100) if t > 0 else 0
            f.write(f"{s:10} | معاملات: {t:4} | نرخ برد: {wr:5.1f}%\n")
        f.write(f"==============================\n📊 مجموع معاملات: {total_trades}")

if __name__ == "__main__": 
    run_backtest()

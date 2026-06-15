# ---------------------------------------------------------
# FILE PATH: src/optimizer.py (v8.5 - Fixed LightGBM Alignment & Safe Copy)
# ---------------------------------------------------------
import os
import sys
import json
import sqlite3
import pandas as pd
import numpy as np

# تنظیم مسیر پایه جهت دسترسی به پکیج‌های پروژه
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
from src import indicators, strategy_utils, backtester
from src.brain import TradingBrain

def evaluate_parameters(symbol, df, adx_th, swing_w):
    """
    ارزیابی سریع ترکیب پارامترها بر روی دیتای بکتست با ساختار ستون‌های LightGBM
    """
    # شبیه‌سازی فیلترهای اندیکاتور بر اساس پارامترهای جدید
    df_copy = df.copy()
    
    # اطمینان از وجود ستون‌های ویژگی (Features)
    features_list = [
        'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
        'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
        'feat_body_ratio', 'feat_high_volume_session'
    ]
    
    # اگر اندیکاتورها از قبل محاسبه نشده‌اند، مجدداً محاسبه شوند
    if 'feat_adx' not in df_copy.columns:
        df_copy = indicators.calculate_indicators(df_copy)
    
    split_idx = int(len(df_copy) * 0.8)
    
    # بارگذاری مغز مدل برای پیش‌بینی هوشمند در فاز ارزیابی اپتیمایزر
    brain = TradingBrain()
    
    ai_total_trades = 0
    ai_winning_trades = 0
    ai_total_pnl = 0.0
    
    is_in_position = False
    entry_price = 0.0
    direction = ""
    stop_loss = 0.0
    tp2 = 0.0

    # تست پارامترها روی بخش داده‌های آزمایشی (Out-of-Sample)
    for i in range(split_idx, len(df_copy)):
        current_candle = df_copy.iloc[i]
        close_price = float(current_candle['Close'])
        high_price = float(current_candle['High'])
        low_price = float(current_candle['Low'])

        if is_in_position:
            pnl = 0.0
            closed = False
            if direction == "LONG":
                if low_price <= stop_loss:
                    pnl = ((stop_loss - entry_price) / entry_price) * 100
                    closed = True
                elif high_price >= tp2:
                    pnl = ((tp2 - entry_price) / entry_price) * 100
                    ai_winning_trades += 1
                    closed = True
            elif direction == "SHORT":
                if high_price >= stop_loss:
                    pnl = ((entry_price - stop_loss) / entry_price) * 100
                    closed = True
                elif low_price <= tp2:
                    pnl = ((entry_price - tp2) / entry_price) * 100
                    ai_winning_trades += 1
                    closed = True

            if closed:
                ai_total_pnl += pnl
                ai_total_trades += 1
                is_in_position = False
            continue

        if float(current_candle.get('feat_adx', 0)) < adx_th:
            continue

        df_slice = df_copy.iloc[:i]
        last_swing_high = strategy_utils.find_last_swing(df_slice, 'high', swing_w)
        last_swing_low = strategy_utils.find_last_swing(df_slice, 'low', swing_w)

        if last_swing_high is None or last_swing_low is None:
            continue

        # استخراج امن مقدار ATR
        atr_val = 1.0
        if 'feat_atr_percent' in current_candle:
            atr_val = float(current_candle['feat_atr_percent'])
        elif 'atr' in current_candle:
            atr_val = float(current_candle['atr'])

        sl_dist = 1.5 * atr_val
        is_bullish_momentum = float(current_candle.get('feat_rsi', 50)) > 50
        is_bearish_momentum = float(current_candle.get('feat_rsi', 50)) < 50

        # فیلتر تایید هوش مصنوعی لایت‌جی‌بی‌ام با فرمت دیتافریم مجاز
        ai_approved = False
        if symbol in brain.models:
            try:
                features_df = df_copy.iloc[[i]][features_list]
                ai_approved = brain.predict_signal(symbol, features_df)
            except:
                ai_approved = False
        else:
            ai_approved = True

        if high_price > last_swing_high and is_bullish_momentum and ai_approved:
            is_in_position = True
            direction = "LONG"
            entry_price = last_swing_high
            stop_loss = entry_price - sl_dist
            tp2 = entry_price + (sl_dist * 2)
        elif low_price < last_swing_low and is_bearish_momentum and ai_approved:
            is_in_position = True
            direction = "SHORT"
            entry_price = last_swing_low
            stop_loss = entry_price + sl_dist
            tp2 = entry_price - (sl_dist * 2)

    return ai_total_pnl, ai_total_trades

def optimize_all_symbols():
    print("⚙️ شروع بهینه‌سازی هوشمند پارامترهای استراتژی برای LightGBM...")
    
    # فضاهای تست پارامترها
    adx_options = [20, 22, 25]
    swing_options = [5, 7, 10]
    
    best_params_dict = {}
    
    # لود کردن تنظیمات قدیمی در صورت وجود
    params_file = os.path.join(config.BASE_DIR, "best_params.json")
    if os.path.exists(params_file):
        try:
            with open(params_file, "r") as f:
                best_params_dict = json.load(f)
        except:
            best_params_dict = {}

    for symbol in config.WATCHLIST:
        safe_name = symbol.replace('/', '_')
        file_path = os.path.join(config.BASE_DIR, "data", "4h", f"{safe_name}_history.csv")
        
        # 🛠️ اصلاح: بررسی وجود فایل دیتا جهت جلوگیری از خطای AttributeError روی مقدار None
        if not os.path.exists(file_path):
            print(f"⚠️ دیتای تاریخچه برای {symbol} یافت نشد، عبور از اپتیمایزر.")
            continue
            
        df = pd.read_csv(file_path)
        if len(df) < 250:
            continue
            
        df = indicators.calculate_indicators(df)

        best_pnl = -99999.0
        best_adx = config.ADX_THRESHOLD
        best_swing = config.SWING_WINDOW
        
        for adx_th in adx_options:
            for swing_w in swing_options:
                pnl, trades = evaluate_parameters(symbol, df, adx_th, swing_w)
                
                # معیار سنجش: بیشترین سود کل به شرط داشتن حداقل ۲ معامله در فاز تست
                if trades >= 2 and pnl > best_pnl:
                    best_pnl = pnl
                    best_adx = adx_th
                    best_swing = swing_w
                    
        print(f"🎯 بهترین تنظیمات برای {symbol} -> ADX: {best_adx} | Swing Window: {best_swing} | سود فاز تست: {best_pnl:.2f}%")
        
        best_params_dict[symbol] = {
            "ADX_THRESHOLD": int(best_adx),
            "SWING_WINDOW": int(best_swing)
        }

    # ذخیره نهایی فایل پارامترهای بهینه شده برای لایو و بکتست‌های بعدی
    with open(params_file, "w") as f:
        json.dump(best_params_dict, f, indent=4)
    print("✅ فایل تنظیمات داینامیک ربات (best_params.json) با موفقیت به‌روزرسانی شد.")

if __name__ == "__main__":
    optimize_all_symbols()

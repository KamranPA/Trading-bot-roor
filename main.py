# main.py - نسخه نهایی مانیتورینگ شده v6.3.2

import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import joblib

# تنظیم مسیرها
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path: sys.path.append(CURRENT_DIR)
SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path: sys.path.append(SRC_DIR)

import config
from src import database, coinex_client, strategy, telegram_bot, indicators, train_model

def run_bot():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 شروع چرخه جدید ربات")
    
    # ۱. پایش وضعیت دیتابیس
    database.init_db()

    # ۲. مانیتورینگ پوزیشن‌های باز
    update_open_positions()

    # ۳. اسکن بازار
    for pair in config.WATCHLIST:
        symbol = pair.split('/')[0]
        print(f"🔍 در حال تحلیل: {symbol}...")
        
        try:
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty:
                print(f"❌ خطا: دریافت دیتا برای {pair} ناموفق بود.")
                continue
            
            df = indicators.calculate_indicators(df)
            
            # --- بخش مانیتورینگ جدید ---
            signal = strategy.generate_signal(df, pair)
            if signal:
                print(f"✅ سیگنال پیدا شد: {signal}")
            else:
                print(f"ℹ️ برای {pair} سیگنالی یافت نشد.")
            # ---------------------------
            
            if signal:
                # بررسی قفل ۸ ساعته
                if is_telegram_locked_8h(symbol):
                    print(f"🔏 محدودیت ۸ ساعته برای {symbol} فعال است.")
                    database.log_scan(symbol, "Locked 8h")
                    continue
                
                # بررسی هوش مصنوعی
                ai_approved, prob = check_ai_permission(
                    signal['feat_adx'], signal['feat_vol_ratio'], 
                    signal['feat_atr_percent'], signal['feat_rsi'], signal['feat_trend_line']
                )
                
                if not ai_approved:
                    print(f"🚫 سیگنال {symbol} توسط هوش مصنوعی رد شد (Confidence: {prob:.2f})")
                    database.log_scan(symbol, f"AI Rejected {prob:.2f}")
                    continue
                
                # ثبت در دیتابیس
                database.save_signal_advanced(
                    symbol=symbol, direction=signal['direction'],
                    entry_price=signal['entry_price'], stop_loss=signal['stop_loss'],
                    tp1=signal['tp1'], tp2=signal['tp2'],
                    feat_adx=signal['feat_adx'], feat_vol_ratio=signal['feat_vol_ratio'],
                    feat_atr_percent=signal['feat_atr_percent'], feat_rsi=signal['feat_rsi'],
                    feat_trend_line=signal['feat_trend_line'], status="OPEN"
                )
                print(f"💾 سیگنال {symbol} با موفقیت در دیتابیس ذخیره شد.")
                telegram_bot.format_and_send_signal(signal)
            else:
                database.log_scan(symbol, "No Signal")
                
        except Exception as e:
            print(f"❌ خطای بحرانی در تحلیل {symbol}: {e}")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🏁 پایان چرخه.")

# [اطمینان حاصل کنید که توابع check_ai_permission, update_open_positions و is_telegram_locked_8h در ادامه همین فایل قرار دارند]

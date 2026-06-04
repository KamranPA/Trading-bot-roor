# main.py
# فایل اصلی اجرای ربات (نسخه v3.6 - اصلاح تداخل ماژول دیتابیس در گیت‌هاب اکشنز)

import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime

# تنظیم دقیق و مستقل مسیرهای پروژه برای جلوگیری از تداخل لود ماژول‌ها
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

# ایمپورت‌های کالیبره‌شده برای سرور لینوکس گیت‌هاب
import config
from src import database          # 🛠️ اصلاح اصلی: فراخوانی مستقیم از پوشه src جهت رفع خطای AttributeError
from src import coinex_client
from src import strategy
from src import telegram_bot
from src import indicators

def update_open_positions():
    """
    بررسی پوزیشن‌های باز، مقایسه قیمت لایو با تارگت‌ها/استاپ،
    محاسبه درصد سود یا ضرر واقعی (PnL) و بستن پوزیشن در دیتابیس برای تغذیه مغز سیستم.
    """
    db_path = database.DB_NAME
    if not os.path.exists(db_path):
        return
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # ۱. دریافت تمام پوزیشن‌های باز (OPEN) از دیتابیس
        cursor.execute("SELECT id, symbol, direction, entry_price, stop_loss FROM signals WHERE status = 'OPEN'")
        open_positions = cursor.fetchall()
        
        if not open_positions:
            print("ℹ️ هیچ پوزیشن بازی در حال حاضر برای بروزرسانی وجود ندارد.")
            conn.close()
            return
            
        print(f"\n🔄 در حال بررسی و مدیریت وضعیت {len(open_positions)} پوزیشن باز در بازار لایو...")
        
        for pos in open_positions:
            pos_id, symbol, direction, entry_price, stop_loss = pos
            pair = f"{symbol}/USDT"
            
            # دریافت کندل لایو از صرافی کوئینکس
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty:
                print(f"⚠️ خطای دریافت قیمت لایو برای جفت‌ارز {pair}")
                continue
                
            current_price = df.iloc[-1]['Close']
            
            # دریافت تارگت‌های اختصاصی پوزیشن از جدول signal_targets
            cursor.execute("SELECT target_number, target_price FROM signal_targets WHERE signal_id = ?", (pos_id,))
            targets = {row[0]: row[1] for row in cursor.fetchall()}
            tp1 = targets.get(1)
            tp2 = targets.get(2)
            
            closed = False
            pnl = 0.0
            reason = ""
            
            # ۲. محاسبات ریاضی خروج و ارزیابی لایو حد سود و حد ضرر
            if direction == 'LONG':
                if current_price <= stop_loss:  # برخورد با حد ضرر
                    closed = True
                    pnl = ((stop_loss - entry_price) / entry_price) * 100
                    reason = "SL Hit"
                elif tp2 and current_price >= tp2:  # برخورد با تارگت دوم (اصلی)
                    closed = True
                    pnl = ((tp2 - entry_price) / entry_price) * 100
                    reason = "TP2 Hit"
                elif tp1 and current_price >= tp1:  # برخورد با تارگت اول
                    closed = True
                    pnl = ((tp1 - entry_price) / entry_price) * 100
                    reason = "TP1 Hit"
                    
            elif direction == 'SHORT':
                if current_price >= stop_loss:  # برخورد با حد ضرر در موقعیت فروش
                    closed = True
                    pnl = ((entry_price - stop_loss) / entry_price) * 100
                    reason = "SL Hit"
                elif tp2 and current_price <= tp2:  # برخورد با تارگت دوم
                    closed = True
                    pnl = ((entry_price - tp2) / entry_price) * 100
                    reason = "TP2 Hit"
                elif tp1 and current_price <= tp1:  # برخورد با تارگت اول
                    closed = True
                    pnl = ((entry_price - tp1) / entry_price) * 100
                    reason = "TP1 Hit"
            
            # ۳. اعمال فیزیکی بستن پوزیشن در صورت تاچ شدن سطوح قیمتی
            if closed:
                # بروزرسانی جدول اصلی سیگنال‌ها
                cursor.execute("""
                    UPDATE signals 
                    SET status = 'CLOSED', closed_at = ?, pnl_percent = ?
                    WHERE id = ?
                """, (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), round(pnl, 2), pos_id))
                
                # بروزرسانی وضعیت تارگت‌ها در جدول تفکیکی
                target_status = "HIT" if "TP" in reason else "FAILED"
                cursor.execute("UPDATE signal_targets SET status = ? WHERE signal_id = ?", (target_status, pos_id))
                
                print(f"🚨 [POSITION CLOSED] ارز {symbol} بسته شد | علت: {reason} | بازدهی: {pnl:.2f}%")
            else:
                print(f"📊 ارز {symbol} در پوزیشن {direction} باز است | قیمت ورود: {entry_price} | قیمت فعلی: {current_price}")
                
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ خطا در پردازش متد بروزرسانی پوزیشن‌های باز دیتابیس: {e}")

def is_telegram_locked_8h(symbol, hours_limit=8):
    """بررسی هوشمند اختلاف زمان آخرین پوزیشن بر پایه UTC جهت جلوگیری از اسپم در بازه زمانی مشخص"""
    db_path = database.DB_NAME
    if not os.path.exists(db_path):
        return False
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        query = "SELECT timestamp FROM signals WHERE symbol = ? ORDER BY id DESC LIMIT 1"
        cursor.execute(query, (symbol,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            clean_time_str = str(result[0]).replace('T', ' ').split('.')[0]
            try:
                last_signal_time = datetime.strptime(clean_time_str, '%Y-%m-%d %H:%M:%S')
            except Exception:
                return False
                
            time_difference = datetime.utcnow() - last_signal_time
            hours_passed = time_difference.total_seconds() / 3600
            
            print(f"⏱️ [Filter Check] برای {symbol}: {hours_passed:.2f} ساعت از آخرین پوزیشن گذشته است.")
            
            if hours_passed < hours_limit:
                print(f"🔒 [Locked] ارسال سیگنال تکراری {symbol} به تلگرام مسدود شد.")
                return True
                
        return False
    except Exception as e:
        print(f"⚠️ خطا در بررسی فیلتر زمانی تلگرام: {e}")
        return False

def run_bot():
    print("🤖 اسکنر هوشمند نسخه v3.6 (مجهز به بازخورد PnL و ضد اسپم UTC) فعال شد...")
    
    # فراخوانی متدها مستقیماً از نمونه ایمپورت شده سورس داخلی
    database.init_db()
    database.check_filters_lock()
    
    # بررسی زنده وضعیت کلی ربات از تنظیمات جدول دیتابیس
    bot_mode = str(database.get_setting("bot_status", "ACTIVE")).strip().upper()
    if bot_mode != "ACTIVE":
        print("🛑 ربات از طریق تنظیمات دیتابیس غیرفعال شده است.")
        return
    
    # ابتدا بررسی پوزیشن‌های باز قدیمی و آپدیت سود و ضررها در دیتابیس برای تغذیه مغز
    update_open_positions()
    
    print("\n🔍 شروع فرآیند اسکن بازار و جفت‌ارزهای واچ‌لیست...")
    # گردش داینامیک روی لیست تحت نظر واچ‌لیست سیستم
    for pair in config.WATCHLIST:
        symbol = pair.split('/')[0]  # جداسازی کلمه اصلی ارز نظیر BTC
        print(f"\n🔄 پردازش تکنیکال و محاسباتی: {pair}...")
        
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty:
            print(f"❌ دیتایی برای جفت‌ارز {pair} دریافت نشد.")
            continue
            
        # محاسبه اندیکاتورهای مستقل (ATR, ADX, Volume MA)
        df = indicators.calculate_indicators(df)
        
        # بررسی شکست سطوح سوئینگ و تولید خروجی استراتژی
        signal_result = strategy.generate_signal(df, pair)
        
        if signal_result and isinstance(signal_result, dict):
            direction = signal_result['direction']
            print(f"🎯 استراتژی روی {symbol} سیگنال {direction} صادر کرد.")
            
            # ۱. ثبت لاگ اولیه اسکن در دیتابیس
            database.log_scan(symbol, f"Signal {direction} | Entry: {signal_result['entry_price']}")
            
            # ۲. اعمال فیلتر زمانی ضد اسپم ۸ ساعته کالیبره شده با UTC سرور
            if is_telegram_locked_8h(symbol, hours_limit=8):
                print(f"⏭️ ارسال به تلگرام مسدود شد: فیلتر ۸ ساعته برای {symbol} فعال است.")
                continue
                
            # ۳. ذخیره‌سازی داده‌ها در معماری تفکیکی و ۴ جدوله دیتابیس با زمان استاندارد
            database.save_signal_advanced(
                symbol=symbol,
                direction=direction,
                entry_price=signal_result['entry_price'],
                stop_loss=signal_result['stop_loss'],
                tp1=signal_result['tp1'],
                tp2=signal_result['tp2'],
                status="OPEN"
            )
            
            # ۴. فرمت‌بندی فارسی و ارسال سیگنال لایو به تلگرام
            telegram_bot.format_and_send_signal(signal_result)
            
        else:
            print(f"🔍 ارز {symbol} شرایط ورود به معامله را نداشت.")
            database.log_scan(symbol, "No Signal")
            
    print("\n🏁 فرآیند دوره جاری اسکن بازار به پایان رسید.")

if __name__ == "__main__":
    run_bot()

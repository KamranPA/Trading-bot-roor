# main.py
# نسخه کاملاً یکپارچه، جامع و بدون نقص v6.3 (اصلاح فیلتر زمان و پایداری کامل سیستم)

import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import joblib

# تنظیم مسیرهای اصلی پروژه جهت بارگذاری بدون مشکل ماژول‌ها
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

import config
from src import database
from src import coinex_client
from src import strategy
from src import telegram_bot
from src import indicators
from src import train_model

MODEL_PATH = os.path.join(CURRENT_DIR, "src", "models", "trading_filter_model.pkl")

def check_ai_permission(feat_adx, feat_vol_ratio, feat_atr_percent, feat_rsi, feat_trend_line):
    """🧠 دروازه‌بان هوش مصنوعی ۳۶۰ درجه برای فیلتر شکست‌های فیک"""
    if not os.path.exists(MODEL_PATH):
        print("ℹ️ مدل هوش مصنوعی هنوز آموزش ندیده است؛ تایید خودکار سیگنال.")
        return True, 1.0

    try:
        model = joblib.load(MODEL_PATH)
        input_data = pd.DataFrame([{
            'feat_adx': feat_adx,
            'feat_vol_ratio': feat_vol_ratio,
            'feat_atr_percent': feat_atr_percent,
            'feat_rsi': feat_rsi,
            'feat_trend_line': feat_trend_line
        }])
        
        prediction = model.predict(input_data)[0]
        probabilities = model.predict_proba(input_data)[0]
        return (True, probabilities[1]) if prediction == 1 else (False, probabilities[1])
    except Exception as e:
        print(f"⚠️ خطا در ارزیابی مدل هوش مصنوعی: {e}")
        return True, 1.0

def update_open_positions():
    """🛡️ مکانیزم ریسک‌فری خودکار و مدیریت خروج پوزیشن‌های باز"""
    db_path = database.DB_NAME
    if not os.path.exists(db_path):
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, symbol, direction, entry_price, stop_loss FROM signals WHERE status = 'OPEN'")
        open_positions = cursor.fetchall()
        
        for pos in open_positions:
            pos_id, symbol, direction, entry_price, stop_loss = pos
            pair = f"{symbol}/USDT"
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty:
                continue
                
            current_price = float(df.iloc[-1]['Close'])
            cursor.execute("SELECT target_number, target_price, status FROM signal_targets WHERE signal_id = ?", (pos_id,))
            targets_data = cursor.fetchall()
            targets = {row[0]: row[1] for row in targets_data}
            targets_status = {row[0]: row[2] for row in targets_data}
            
            tp1, tp2 = targets.get(1), targets.get(2)
            closed, pnl, reason = False, 0.0, ""
            
            if direction == 'LONG':
                if tp1 and current_price >= tp1 and targets_status.get(1) == 'PENDING':
                    cursor.execute("UPDATE signal_targets SET status = 'HIT' WHERE signal_id = ? AND target_number = 1", (pos_id,))
                    cursor.execute("UPDATE signals SET stop_loss = ? WHERE id = ?", (entry_price, pos_id))
                    stop_loss = entry_price
                    telegram_bot.send_telegram_message(f"🛡️ **ریسک‌فری خودکار #{symbol}**\n✅ TP1 لمس شد. استاپ به نقطه ورود ({entry_price}) منتقل شد.")
                
                if current_price <= stop_loss:
                    closed, reason = True, "Stop Loss Hit"
                    pnl = ((stop_loss - entry_price) / entry_price) * 100
                elif tp2 and current_price >= tp2:
                    closed, reason = True, "TP2 Hit"
                    pnl = ((tp2 - entry_price) / entry_price) * 100
                    
            elif direction == 'SHORT':
                if tp1 and current_price <= tp1 and targets_status.get(1) == 'PENDING':
                    cursor.execute("UPDATE signal_targets SET status = 'HIT' WHERE signal_id = ? AND target_number = 1", (pos_id,))
                    cursor.execute("UPDATE signals SET stop_loss = ? WHERE id = ?", (entry_price, pos_id))
                    stop_loss = entry_price
                    telegram_bot.send_telegram_message(f"🛡️ **ریسک‌فری خودکار #{symbol}**\n✅ TP1 لمس شد. استاپ به نقطه ورود ({entry_price}) منتقل شد.")
                
                if current_price >= stop_loss:
                    closed, reason = True, "Stop Loss Hit"
                    pnl = ((entry_price - stop_loss) / entry_price) * 100
                elif tp2 and current_price <= tp2:
                    closed, reason = True, "TP2 Hit"
                    pnl = ((entry_price - tp2) / entry_price) * 100
            
            if closed:
                cursor.execute("UPDATE signals SET status = 'CLOSED', closed_at = ?, pnl_percent = ? WHERE id = ?", 
                               (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), round(pnl, 2), pos_id))
                telegram_bot.send_telegram_message(f"🚪 **خروج پوزیشن #{symbol}**\nعلت: {reason}\nبازدهی: {pnl:.2f}%")
                
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ خطا در بروزرسانی معاملات: {e}")

def is_telegram_locked_8h(symbol, hours_limit=8):
    """🔏 بررسی قفل ۸ ساعته بر اساس زمان آخرین سیگنال صادر شده زنده در جدول اصلی"""
    db_path = database.DB_NAME
    if not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # ما فقط زمان ثبت معاملات واقعی در جدول اصلی را چک می‌کنیم، نه لاگ‌های اسکن عادی را
        cursor.execute("SELECT timestamp FROM signals WHERE symbol = ? ORDER BY id DESC LIMIT 1", (symbol,))
        res = cursor.fetchone()
        conn.close()
        
        if res and res[0]:
            t_str = str(res[0]).replace('T', ' ').split('.')[0]
            last_time = datetime.strptime(t_str, '%Y-%m-%d %H:%M:%S')
            if (datetime.utcnow() - last_time) < timedelta(hours=hours_limit):
                return True
        return False
    except Exception:
        return False

def run_bot():
    print("🤖 اسکنر هوشمند نسخه v6.3 فعال شد...")
    
    # اولویت اول: بررسی ساختار پایگاه داده و ساخت ستون‌ها در صورت عدم وجود
    database.init_db()
    if str(database.get_setting("bot_status", "ACTIVE")).strip().upper() != "ACTIVE":
        print("🛑 ربات از طریق دیتابیس غیرفعال شده است.")
        return
    
    # اولویت دوم: مانیتور و ریسک‌فری موقعیت‌های باز
    update_open_positions()
    
    # اولویت سوم: تلاش برای آموزش هوش مصنوعی با بلاک محافظتی try/except برای جلوگیری از کرش کل فرآیند
    try:
        train_model.train_ai_model()
    except Exception as e:
        print(f"ℹ️ موتور هوش مصنوعی منتظر ثبت دیتای بیشتر است: {e}")
    
    # اولویت چهارم: چرخش روی کل واچ‌لیست بدون قفل زودهنگام فرآیند اسکن
    for pair in config.WATCHLIST:
        symbol = pair.split('/')[0]
            
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty:
            continue
            
        df = indicators.calculate_indicators(df)
        signal_result = strategy.generate_signal(df, pair)
        
        # اگر استراتژی چارت ۴ ساعته سیگنال قطعی صادر کرد
        if signal_result and isinstance(signal_result, dict):
            
            # 🛡️ موقعیت فیلتر زمان اصلاح شد: بررسی قفل تلگرام فقط و فقط هنگام پیدا شدن سیگنال واقعی انجام می‌شود
            if is_telegram_locked_8h(symbol, hours_limit=8):
                print(f"🔏 سیگنال جدید برای {symbol} یافت شد، اما به علت محدودیت ارسال ۸ ساعته تلگرام، بلاک گردید.")
                database.log_scan(symbol, "Signal Found (Blocked by 8h Telegram Lock)")
                continue
                
            # ارزیابی توسط سنسورهای هوش مصنوعی
            ai_approved, win_rate = check_ai_permission(
                feat_adx=signal_result['feat_adx'], feat_vol_ratio=signal_result['feat_vol_ratio'],
                feat_atr_percent=signal_result['feat_atr_percent'], feat_rsi=signal_result['feat_rsi'],
                feat_trend_line=signal_result['feat_trend_line']
            )
            
            if not ai_approved:
                database.log_scan(symbol, f"Blocked by AI ({win_rate*100:.1f}%)")
                continue
            
            # ذخیره نهایی پوزیشن در دیتابیس
            database.save_signal_advanced(
                symbol=symbol, direction=signal_result['direction'],
                entry_price=signal_result['entry_price'], stop_loss=signal_result['stop_loss'],
                tp1=signal_result['tp1'], tp2=signal_result['tp2'],
                feat_adx=signal_result['feat_adx'], feat_vol_ratio=signal_result['feat_vol_ratio'],
                feat_atr_percent=signal_result['feat_atr_percent'], feat_rsi=signal_result['feat_rsi'],
                feat_trend_line=signal_result['feat_trend_line'], status="OPEN"
            )
            
            # ارسال نهایی به کانال تلگرام شما
            telegram_bot.format_and_send_signal(signal_result)
        else:
            # اسکن‌های معمولی بازار که سیگنال ندارند، بدون هیچ مشکلی فقط لاگ می‌شوند
            database.log_scan(symbol, "No Signal")

if __name__ == "__main__":
    run_bot()

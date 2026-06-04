# main.py
# فایل اصلی اجرای ربات (نسخه v6.0 - مجهز به هوش مصنوعی ۳۶۰ درجه و مدیریت ریسک توزیع‌شده Trailing Stop)

import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime
import joblib

# تنظیم مسیرهای اصلی پروژه جهت جلوگیری از ارورهای ایمپورت ماژول
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
    """🧠 دروازه‌بان هوش مصنوعی ۳۶۰ درجه: بررسی شکست با ۵ ویژگی قدرتمند تکنیکال"""
    if not os.path.exists(MODEL_PATH):
        print("ℹ️ مدل هوش مصنوعی یافت نشد؛ سیگنال با فیلترهای کلاسیک ارزیابی می‌شود.")
        return True, 1.0

    try:
        model = joblib.load(MODEL_PATH)
        
        # ساخت دیتافریم منطبق بر ویژگی‌های زمان آموزش مدل
        input_data = pd.DataFrame([{
            'feat_adx': feat_adx,
            'feat_vol_ratio': feat_vol_ratio,
            'feat_atr_percent': feat_atr_percent,
            'feat_rsi': feat_rsi,
            'feat_trend_line': feat_trend_line
        }])
        
        prediction = model.predict(input_data)[0]
        probabilities = model.predict_proba(input_data)[0]
        win_probability = probabilities[1]
        
        if prediction == 1:
            print(f"🟢 [AI APPROVED] هوش مصنوعی سیگنال را تایید کرد! (احتمال برد: {win_probability*100:.1f}%)")
            return True, win_probability
        else:
            print(f"🔴 [AI BLOCKED] هوش مصنوعی مانع شکست فیک شد! (احتمال برد: {win_probability*100:.1f}%)")
            return False, win_probability
            
    except Exception as e:
        print(f"⚠️ خطا در ارزیابی مدل هوش مصنوعی: {e}")
        return True, 1.0

def update_open_positions():
    """🛡️ مکانیزم مدیریت ریسک پیشرفته: بررسی پوزیشن‌های باز، ریسک‌فری خودکار و خروج در تارگت‌ها"""
    db_path = database.DB_NAME
    if not os.path.exists(db_path):
        return
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # ۱. استخراج پوزیشن‌های باز از دیتابیس
        cursor.execute("SELECT id, symbol, direction, entry_price, stop_loss FROM signals WHERE status = 'OPEN'")
        open_positions = cursor.fetchall()
        
        if not open_positions:
            conn.close()
            return
            
        for pos in open_positions:
            pos_id, symbol, direction, entry_price, stop_loss = pos
            pair = f"{symbol}/USDT"
            
            # دریافت قیمت لحظه‌ای از صرافی کوین‌اکس
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty:
                continue
                
            current_price = float(df.iloc[-1]['Close'])
            
            # استخراج تارگت‌های مربوط به این پوزیشن
            cursor.execute("SELECT target_number, target_price, status FROM signal_targets WHERE signal_id = ?", (pos_id,))
            targets_data = cursor.fetchall()
            
            targets = {row[0]: row[1] for row in targets_data}
            targets_status = {row[0]: row[2] for row in targets_data}
            
            tp1 = targets.get(1)
            tp2 = targets.get(2)
            
            closed = False
            pnl = 0.0
            reason = ""
            
            # 🟢 سناریوی معاملات خرید (LONG)
            if direction == 'LONG':
                # الف) بررسی فعال‌سازی ریسک‌فری خودکار (قیمت به TP1 رسیده اما وضعیت آن PENDING است)
                if tp1 and current_price >= tp1 and targets_status.get(1) == 'PENDING':
                    cursor.execute("UPDATE signal_targets SET status = 'HIT' WHERE signal_id = ? AND target_number = 1", (pos_id,))
                    cursor.execute("UPDATE signals SET stop_loss = ? WHERE id = ?", (entry_price, pos_id))
                    stop_loss = entry_price # همگام‌سازی متغیر محلی برای ادامه پردازش کندل فعلی
                    
                    telegram_bot.send_telegram_message(
                        f"🛡️ **عملیات ریسک‌فری خودکار (Risk-Free)**\n\n"
                        f"🔹 جفت ارز: #{symbol}\n"
                        f"✅ تارگت اول (TP1) با موفقیت لمس شد.\n"
                        f"📉 حد ضرر (SL) برای امنیت کامل حساب به **نقطه ورود ({entry_price})** منتقل شد. معامله کاملاً بیمه است! 👌"
                    )
                
                # ب) بررسی فعال شدن حد ضرر (اصلی یا ریسک‌فری شده)
                if current_price <= stop_loss:
                    closed = True
                    pnl = ((stop_loss - entry_price) / entry_price) * 100
                    reason = "Stop Loss Hit (حد ضرر یا ریسک‌فری)"
                
                # ج) بررسی لمس تارگت نهایی و اصلی
                elif tp2 and current_price >= tp2:
                    closed = True
                    pnl = ((tp2 - entry_price) / entry_price) * 100
                    reason = "تارگت دوم (TP2 Hit)"
                    
            # 🔴 سناریوی معاملات فروش (SHORT)
            elif direction == 'SHORT':
                # الف) بررسی فعال‌سازی ریسک‌فری خودکار
                if tp1 and current_price <= tp1 and targets_status.get(1) == 'PENDING':
                    cursor.execute("UPDATE signal_targets SET status = 'HIT' WHERE signal_id = ? AND target_number = 1", (pos_id,))
                    cursor.execute("UPDATE signals SET stop_loss = ? WHERE id = ?", (entry_price, pos_id))
                    stop_loss = entry_price
                    
                    telegram_bot.send_telegram_message(
                        f"🛡️ **عملیات ریسک‌فری خودکار (Risk-Free)**\n\n"
                        f"🔹 جفت ارز: #{symbol}\n"
                        f"✅ تارگت اول (TP1) با موفقیت لمس شد.\n"
                        f"📈 حد ضرر (SL) برای امنیت کامل حساب به **نقطه ورود ({entry_price})** منتقل شد. معامله کاملاً بیمه است! 👌"
                    )
                
                # ب) بررسی فعال شدن حد ضرر
                if current_price >= stop_loss:
                    closed = True
                    pnl = ((entry_price - stop_loss) / entry_price) * 100
                    reason = "Stop Loss Hit (حد ضرر یا ریسک‌فری)"
                
                # ج) بررسی لمس تارگت نهایی
                elif tp2 and current_price <= tp2:
                    closed = True
                    pnl = ((entry_price - tp2) / entry_price) * 100
                    reason = "تارگت دوم (TP2 Hit)"
            
            # اگر پوزیشن در این اسکن بسته شده باشد
            if closed:
                cursor.execute("""
                    UPDATE signals 
                    SET status = 'CLOSED', closed_at = ?, pnl_percent = ?
                    WHERE id = ?
                """, (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), round(pnl, 2), pos_id))
                
                final_status = "HIT" if "TP2" in reason else "FAILED"
                cursor.execute("UPDATE signal_targets SET status = ? WHERE signal_id = ? AND target_number = 2", (final_status, pos_id))
                
                # ارسال بیانیه خروج به تلگرام شما
                status_emoji = "💎" if "TP2" in reason else "🚪"
                telegram_bot.send_telegram_message(
                    f"{status_emoji} **خروج از پوزیشن معاملاتی**\n\n"
                    f"🔹 جفت ارز: #{symbol}\n"
                    f"🔸 موقعیت: {direction}\n"
                    f"💡 علت خروج: {reason}\n"
                    f"💰 بازدهی نهایی پوزیشن: **{pnl:.2f}%**"
                )
                print(f"🚨 [POSITION CLOSED] ارز {symbol} بسته شد | علت: {reason} | بازدهی: {pnl:.2f}%")
                
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ خطا در مدیریت ریسک و بروزرسانی معاملات: {e}")

def is_telegram_locked_8h(symbol, hours_limit=8):
    """🔏 جلوگیری از ارسال سیگنال‌های تکراری و هم‌پوشان از یک ارز در بازه ۸ ساعته"""
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
            last_signal_time = datetime.strptime(clean_time_str, '%Y-%m-%d %H:%M:%S')
            time_difference = datetime.utcnow() - last_signal_time
            if (time_difference.total_seconds() / 3600) < hours_limit:
                return True
        return False
    except Exception:
        return False

def run_bot():
    print("🤖 اسکنر هوشمند نسخه v6.0 (دید ۳۶۰ درجه هوش مصنوعی + Trailing Stop لایو) فعال شد...")
    
    # راه‌اندازی دیتابیس کالیبره شده با ساختار جدید
    database.init_db()
    if str(database.get_setting("bot_status", "ACTIVE")).strip().upper() != "ACTIVE":
        print("🛑 ربات از طریق تنظیمات دیتابیس غیرفعال شده است.")
        return
    
    # گام اول: اجرای سیستم مدیریت ریسک روی پوزیشن‌های باز قبلی
    update_open_positions()
    
    # گام دوم: بررسی خودکار نیاز به بازآموزی مدل یادگیری ماشین
    train_model.train_ai_model()
    
    # گام سوم: اسکن چرخشی واچ‌لیست ارزها
    for pair in config.WATCHLIST:
        symbol = pair.split('/')[0]
        
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty:
            continue
            
        df = indicators.calculate_indicators(df)
        signal_result = strategy.generate_signal(df, pair)
        
        # اگر استراتژی کلاسیک سیگنال معتبری پیدا کرد
        if signal_result and isinstance(signal_result, dict):
            direction = signal_result['direction']
            
            # استعلام فیلترینگ هوشمند ۵ فاکتوره از هوش مصنوعی
            ai_approved, win_rate = check_ai_permission(
                feat_adx=signal_result['feat_adx'],
                feat_vol_ratio=signal_result['feat_vol_ratio'],
                feat_atr_percent=signal_result['feat_atr_percent'],
                feat_rsi=signal_result['feat_rsi'],
                feat_trend_line=signal_result['feat_trend_line']
            )
            
            if not ai_approved:
                database.log_scan(symbol, f"Blocked by AI (Est Win: {win_rate*100:.1f}%)")
                continue
            
            # ذخیره پوزیشن تایید شده در دیتابیس
            database.save_signal_advanced(
                symbol=symbol, direction=direction,
                entry_price=signal_result['entry_price'], stop_loss=signal_result['stop_loss'],
                tp1=signal_result['tp1'], tp2=signal_result['tp2'],
                feat_adx=signal_result['feat_adx'], feat_vol_ratio=signal_result['feat_vol_ratio'],
                feat_atr_percent=signal_result['feat_atr_percent'], feat_rsi=signal_result['feat_rsi'],
                feat_trend_line=signal_result['feat_trend_line'], status="OPEN"
            )
            
            # بررسی قفل زمانی ۸ ساعته کانال تلگرام برای این ارز
            if is_telegram_locked_8h(symbol, hours_limit=8):
                print(f"ℹ️ سیگنال {symbol} در دیتابیس ثبت شد اما به دلیل قفل ۸ ساعته تلگرام، ارسال نشد.")
                continue
                
            # ارسال پیام شکیل سیگنال به تلگرام
            telegram_bot.format_and_send_signal(signal_result)
        else:
            database.log_scan(symbol, "No Signal")

if __name__ == "__main__":
    run_bot()

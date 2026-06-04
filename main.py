# main.py
# فایل اصلی اجرای ربات (نسخه v5.5 - مجهز به سیستم فیلترینگ هوشمند لایو با یادگیری ماشین)

import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime
import joblib  # 🧠 ایمپورت کتابخانه لود مدل‌های هوش مصنوعی

# تنظیم دقیق و مستقل مسیرهای پروژه برای جلوگیری از تداخل لود ماژول‌ها
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

# ایمپورت‌های کالیبره‌شده برای سرور لینوکس گیت‌هاب
import config
from src import database
from src import coinex_client
from src import strategy
from src import telegram_bot
from src import indicators
from src import train_model  # ایمپورت اسکریپت آموزش برای بهینه‌سازی همزمان

MODEL_PATH = os.path.join(CURRENT_DIR, "src", "models", "trading_filter_model.pkl")

def check_ai_permission(feat_adx, feat_vol_ratio, feat_atr_percent):
    """🧠 دروازه‌بان هوش مصنوعی: بررسی سیگنال با مدل یادگیری ماشین"""
    if not os.path.exists(MODEL_PATH):
        # اگر هنوز مدلی آموزش داده نشده، با زدن رای مثبت اجازه عبور می‌دهیم تا دیتا جمع شود
        print("ℹ️ مدل هوش مصنوعی یافت نشد؛ سیگنال با فیلترهای کلاسیک ارزیابی می‌شود.")
        return True, 1.0

    try:
        # لود مغز الکترونیک مدل
        model = joblib.load(MODEL_PATH)
        
        # ساخت دیتافریم تک‌ردیفه دقیقا با همان نام ستون‌هایی که مدل با آن‌ها آموزش دیده است
        input_data = pd.DataFrame([{
            'feat_adx': feat_adx,
            'feat_vol_ratio': feat_vol_ratio,
            'feat_atr_percent': feat_atr_percent
        }])
        
        # پیش‌بینی مدل (1 یعنی سودده، 0 یعنی ضررده/شکست فیک)
        prediction = model.predict(input_data)[0]
        
        # محاسبه درصد احتمال موفقیت معامله توسط مدل
        probabilities = model.predict_proba(input_data)[0]
        win_probability = probabilities[1]  # احتمال کلاس 1 (برد)
        
        if prediction == 1:
            print(f"🟢 [AI APPROVED] هوش مصنوعی سیگنال را تایید کرد! (احتمال برد: {win_probability*100:.1f}%)")
            return True, win_probability
        else:
            print(f"🔴 [AI BLOCKED] هوش مصنوعی جلو این پوزیشن را گرفت! خطر شکست فیک! (احتمال برد: {win_probability*100:.1f}%)")
            return False, win_probability
            
    except Exception as e:
        print(f"⚠️ خطا در ارزیابی مدل هوش مصنوعی: {e}")
        return True, 1.0  # در صورت بروز خطای سیستمی، معامله را مسدود نمی‌کنیم

def update_open_positions():
    """بررسی پوزیشن‌های باز، محاسبه PnL لایو و آپدیت دیتابیس برای تغذیه مدل هوش مصنوعی"""
    db_path = database.DB_NAME
    if not os.path.exists(db_path):
        return
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
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
            
            df = coinex_client.get_coinex_candles(pair)
            if df is None or df.empty:
                print(f"⚠️ خطای دریافت قیمت لایو برای جفت‌ارز {pair}")
                continue
                
            current_price = df.iloc[-1]['Close']
            
            cursor.execute("SELECT target_number, target_price FROM signal_targets WHERE signal_id = ?", (pos_id,))
            targets = {row[0]: row[1] for row in cursor.fetchall()}
            tp1 = targets.get(1)
            tp2 = targets.get(2)
            
            closed = False
            pnl = 0.0
            reason = ""
            
            if direction == 'LONG':
                if current_price <= stop_loss:
                    closed = True
                    pnl = ((stop_loss - entry_price) / entry_price) * 100
                    reason = "SL Hit"
                elif tp2 and current_price >= tp2:
                    closed = True
                    pnl = ((tp2 - entry_price) / entry_price) * 100
                    reason = "TP2 Hit"
                elif tp1 and current_price >= tp1:
                    closed = True
                    pnl = ((tp1 - entry_price) / entry_price) * 100
                    reason = "TP1 Hit"
                    
            elif direction == 'SHORT':
                if current_price >= stop_loss:
                    closed = True
                    pnl = ((entry_price - stop_loss) / entry_price) * 100
                    reason = "SL Hit"
                elif tp2 and current_price <= tp2:
                    closed = True
                    pnl = ((entry_price - tp2) / entry_price) * 100
                    reason = "TP2 Hit"
                elif tp1 and current_price <= tp1:
                    closed = True
                    pnl = ((entry_price - tp1) / entry_price) * 100
                    reason = "TP1 Hit"
            
            if closed:
                cursor.execute("""
                    UPDATE signals 
                    SET status = 'CLOSED', closed_at = ?, pnl_percent = ?
                    WHERE id = ?
                """, (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), round(pnl, 2), pos_id))
                
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
            if hours_passed < hours_limit:
                return True
        return False
    except Exception:
        return False

def run_bot():
    print("🤖 اسکنر هوشمند نسخه v5.5 (مجهز به لایه فیلترینگ یادگیری ماشین پیشرفته) فعال شد...")
    
    database.init_db()
    database.check_filters_lock()
    
    bot_mode = str(database.get_setting("bot_status", "ACTIVE")).strip().upper()
    if bot_mode != "ACTIVE":
        print("🛑 ربات از طریق تنظیمات دیتابیس غیرفعال شده است.")
        return
    
    # ابتدا بررسی و بستن پوزیشن‌های قدیمی برای تولید دیتای زنده آموزش مدل
    update_open_positions()
    
    # 🧠 ترفند طلایی: اجرای خودکار فرآیند یادگیری مجدد مدل هوش مصنوعی بر اساس دیتای جدید دیتابیس
    train_model.train_ai_model()
    
    print("\n🔍 شروع فرآیند اسکن بازار و جفت‌ارزهای واچ‌لیست...")
    for pair in config.WATCHLIST:
        symbol = pair.split('/')[0]
        print(f"\n🔄 پردازش تکنیکال و محاسباتی: {pair}...")
        
        df = coinex_client.get_coinex_candles(pair)
        if df is None or df.empty:
            continue
            
        df = indicators.calculate_indicators(df)
        signal_result = strategy.generate_signal(df, pair)
        
        if signal_result and isinstance(signal_result, dict):
            direction = signal_result['direction']
            
            # 🧠 گام کلیدی: استعلام از دروازه‌بان یادگیری ماشین قبل از هرگونه اقدام عملی
            ai_approved, win_rate = check_ai_permission(
                feat_adx=signal_result['feat_adx'],
                feat_vol_ratio=signal_result['feat_vol_ratio'],
                feat_atr_percent=signal_result['feat_atr_percent']
            )
            
            if not ai_approved:
                # اگر مدل بگوید این معامله به احتمال بالا ضررده است، سیگنال ثبت اسکن می‌شود ولی معامله باز نخواهد شد
                database.log_scan(symbol, f"Blocked by AI (Est Win: {win_rate*100:.1f}%)")
                continue
            
            # ثبت پوزیشن تایید شده توسط هوش مصنوعی در جدول رسمی معاملات
            database.save_signal_advanced(
                symbol=symbol,
                direction=direction,
                entry_price=signal_result['entry_price'],
                stop_loss=signal_result['stop_loss'],
                tp1=signal_result['tp1'],
                tp2=signal_result['tp2'],
                feat_adx=signal_result['feat_adx'],
                feat_vol_ratio=signal_result['feat_vol_ratio'],
                feat_atr_percent=signal_result['feat_atr_percent'],
                status="OPEN"
            )
            
            # فیلتر ضد اسپم تلگرام
            if is_telegram_locked_8h(symbol, hours_limit=8):
                print(f"⏭️ ارسال به تلگرام مسدود شد: فیلتر ۸ ساعته برای {symbol} فعال است.")
                continue
                
            telegram_bot.format_and_send_signal(signal_result)
            
        else:
            print(f"🔍 ارز {symbol} شرایط ورود به معامله را نداشت.")
            database.log_scan(symbol, "No Signal")
            
    print("\n🏁 فرآیند دوره جاری اسکن بازار به پایان رسید.")

if __name__ == "__main__":
    run_bot()

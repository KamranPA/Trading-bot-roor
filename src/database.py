# File Path: /src/database.py
import sqlite3
import os
from datetime import datetime

DB_NAME = "data/trading_bot.db"  # اصلاح مسیر برای هماهنگی با خط لوله گیت‌هاب

def init_db():
    """ایجاد جداول دیتابیس در صورت عدم وجود"""
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                stop_loss REAL,
                status TEXT DEFAULT 'OPEN',
                created_at TEXT,
                closed_at TEXT,
                pnl_percent REAL,
                atr REAL,
                adx REAL,
                rsi REAL,
                ema_diff REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signal_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                target_number INTEGER,
                target_price REAL,
                status TEXT DEFAULT 'PENDING',
                FOREIGN KEY(signal_id) REFERENCES signals(id)
            )
        ''')
        conn.commit()

def save_signal_advanced(symbol, direction, entry_price, stop_loss, tp1, tp2, **indicators_dict):
    """اصلاح شد: تطبیق نام تابع و ساختار آرگومان‌ها با فایل main.py"""
    init_db()
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute('''
                INSERT INTO signals (symbol, direction, entry_price, stop_loss, status, created_at, atr, adx, rsi, ema_diff)
                VALUES (?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?)
            ''', (
                symbol, direction, entry_price, stop_loss, created_at,
                indicators_dict.get('feat_atr_percent', 0.0),
                indicators_dict.get('feat_adx', 0.0),
                indicators_dict.get('feat_rsi', 0.0),
                indicators_dict.get('feat_ema_deviation', 0.0)
            ))
            
            signal_id = cursor.lastrowid
            
            # ذخیره تارگت‌های ۱ و ۲
            for i, target_price in enumerate([tp1, tp2], 1):
                cursor.execute('''
                    INSERT INTO signal_targets (signal_id, target_number, target_price, status)
                    VALUES (?, ?, ?, 'PENDING')
                ''', (signal_id, i, target_price))
                
            conn.commit()
            return signal_id
    except Exception as e:
        print(f"❌ [Database] خطا در ذخیره سیگنال پیشرفته: {e}")
        return None

def get_open_positions_count():
    """تعداد پوزیشن‌های باز برای اعمال محدودیت تعداد معاملات همزمان"""
    init_db()
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'OPEN'")
            return cursor.fetchone()[0]
    except Exception as e:
        print(f"❌ [Database] خطا در دریافت تعداد پوزیشن‌ها: {e}")
        return 0

def manage_open_positions():
    """مدیریت پوزیشن‌های باز: ریسک‌فری در TP1 و بستن پوزیشن در SL یا TP2"""
    from src import coinex_client 
    init_db()
    
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, symbol, direction, entry_price, stop_loss FROM signals WHERE status = 'OPEN'")
            open_trades = cursor.fetchall()
            
            if not open_trades:
                return

            for trade in open_trades:
                trade_id, symbol, direction, entry_price, stop_loss = trade
                
                df = coinex_client.get_coinex_candles(symbol)
                if df is None or df.empty:
                    continue
                    
                current_price = float(df.iloc[-1]['Close'])
                
                cursor.execute("SELECT target_number, target_price, status FROM signal_targets WHERE signal_id = ? ORDER BY target_number", (trade_id,))
                targets = cursor.fetchall()
                
                tp1_price = next((t[1] for t in targets if t[0] == 1), None)
                tp2_price = next((t[1] for t in targets if t[0] == 2), None)
                tp1_status = next((t[2] for t in targets if t[0] == 1), 'PENDING')
                
                close_trade = False
                pnl_percent = 0.0

                if direction == 'LONG':
                    if current_price <= stop_loss:
                        close_trade = True
                        pnl_percent = ((current_price - entry_price) / entry_price) * 100
                    elif tp2_price and current_price >= tp2_price:
                        close_trade = True
                        pnl_percent = ((tp2_price - entry_price) / entry_price) * 100
                    elif tp1_price and current_price >= tp1_price and tp1_status == 'PENDING':
                        cursor.execute("UPDATE signal_targets SET status = 'HIT' WHERE signal_id = ? AND target_number = 1", (trade_id,))
                        cursor.execute("UPDATE signals SET stop_loss = ? WHERE id = ?", (entry_price, trade_id))
                        print(f"🛡️ پوزیشن {symbol} ریسک‌فری شد.")

                elif direction == 'SHORT':
                    if current_price >= stop_loss:
                        close_trade = True
                        pnl_percent = ((entry_price - current_price) / entry_price) * 100
                    elif tp2_price and current_price <= tp2_price:
                        close_trade = True
                        pnl_percent = ((entry_price - tp2_price) / entry_price) * 100
                    elif tp1_price and current_price <= tp1_price and tp1_status == 'PENDING':
                        cursor.execute("UPDATE signal_targets SET status = 'HIT' WHERE signal_id = ? AND target_number = 1", (trade_id,))
                        cursor.execute("UPDATE signals SET stop_loss = ? WHERE id = ?", (entry_price, trade_id))
                        print(f"🛡️ پوزیشن {symbol} ریسک‌فری شد.")

                if close_trade:
                    closed_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute(
                        "UPDATE signals SET status = 'CLOSED', closed_at = ?, pnl_percent = ? WHERE id = ?",
                        (closed_at, round(pnl_percent, 2), trade_id)
                    )
                    conn.commit()
                    print(f"✅ معامله {symbol} بسته شد. PnL: {round(pnl_percent, 2)}%")

    except Exception as e:
        print(f"❌ خطا در اجرای پایش پوزیشن‌ها: {e}")

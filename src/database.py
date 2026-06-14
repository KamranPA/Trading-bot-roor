# FILE: src/database.py
# PURPOSE: SQLite database manager for storing signals, parameters, and live position tracking

import os
import sqlite3
import logging
from datetime import datetime
import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Using absolute path from config to prevent relative directory issues
            self.db_path = config.DB_PATH_LIVE
        else:
            self.db_path = db_path
            
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Initializes database tables if they do not exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Signals and positions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    symbol TEXT,
                    direction TEXT,
                    entry_price REAL,
                    sl REAL,
                    tp1 REAL,
                    tp2 REAL,
                    status TEXT, -- 'OPEN', 'CLOSED', 'TP1_HIT'
                    pnl_percent REAL DEFAULT 0.0,
                    close_reason TEXT DEFAULT ''
                )
            """)
            
            # Execution logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    message TEXT
                )
            """)
            conn.commit()

    def save_signal(self, symbol: str, direction: str, entry_price: float, sl: float, tp1: float, tp2: float) -> bool:
        """Saves a newly generated signal as an OPEN position."""
        # Avoid duplicating open positions for the exact same symbol and direction
        if self.has_open_position(symbol):
            logger.info(f"Signal ignored. Already have an open position for {symbol}")
            return False

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO signals (timestamp, symbol, direction, entry_price, sl, tp1, tp2, status, pnl_percent, close_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', 0.0, '')
            """, (now_str, symbol, direction, entry_price, sl, tp1, tp2))
            conn.commit()
        return True

    def has_open_position(self, symbol: str) -> bool:
        """Checks if there's currently an open position for a symbol."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM signals WHERE symbol = ? AND status IN ('OPEN', 'TP1_HIT')", (symbol,))
            return cursor.fetchone() is not None

    def log_execution(self, message: str):
        """Logs bot activity to the database."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO execution_logs (timestamp, message) VALUES (?, ?)", (now_str, message))
            conn.commit()

    def manage_open_positions(self, coinex_client, telegram_bot) -> list:
        """
        Iterates over all open positions, fetches live prices from CoinEx,
        checks for SL/TP hits, and updates the database & alerts via Telegram.
        Returns a list of messages about closed positions.
        """
        closed_reports = []
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Fetch both fully OPEN positions and partially closed (TP1_HIT) positions
            cursor.execute("SELECT id, timestamp, symbol, direction, entry_price, sl, tp1, tp2, status FROM signals WHERE status IN ('OPEN', 'TP1_HIT')")
            open_positions = cursor.fetchall()
            
            for pos in open_positions:
                pos_id, timestamp, symbol, direction, entry, sl, tp1, tp2, current_status = pos
                
                # Fetch live price from exchange
                live_price = coinex_client.get_current_price(symbol)
                if live_price == 0.0:
                    logger.warning(f"Skipping position monitoring for {symbol} due to exchange ticker error.")
                    continue
                
                is_long = (direction.upper() == "LONG")
                should_close = False
                close_reason = ""
                final_pnl = 0.0
                new_status = current_status

                # --- TRACKING LOGIC ---
                if is_long:
                    # 1. Check Stop Loss
                    if live_price <= sl:
                        should_close = True
                        close_reason = "Stop Loss Hit"
                        final_pnl = ((sl - entry) / entry) * 100.0
                        new_status = "CLOSED"
                    
                    # 2. Check Take Profit 2 (Final Target)
                    elif live_price >= tp2:
                        should_close = True
                        close_reason = "Take Profit 2 Hit (Target Complete)"
                        final_pnl = ((tp2 - entry) / entry) * 100.0
                        new_status = "CLOSED"
                    
                    # 3. Check Take Profit 1 (Partial/Trail Target)
                    elif current_status == "OPEN" and live_price >= tp1:
                        new_status = "TP1_HIT"
                        partial_pnl = ((tp1 - entry) / entry) * 100.0
                        # Trailing mechanism: Move SL to Entry to guarantee risk-free trade
                        sl = entry 
                        
                        cursor.execute("UPDATE signals SET status = 'TP1_HIT', sl = ?, pnl_percent = ? WHERE id = ?", (sl, partial_pnl, pos_id))
                        conn.commit()
                        
                        msg = f"🎯 [TP1 HIT] {symbol} Long reached TP1 at {live_price:.4f}! PnL: +{partial_pnl:.2f}%. Moving SL to Entry ({sl:.4f})."
                        telegram_bot.send_message(msg)
                        closed_reports.append(msg)

                else: # SHORT Position
                    # 1. Check Stop Loss
                    if live_price >= sl:
                        should_close = True
                        close_reason = "Stop Loss Hit"
                        final_pnl = ((entry - sl) / entry) * 100.0
                        new_status = "CLOSED"
                    
                    # 2. Check Take Profit 2
                    elif live_price <= tp2:
                        should_close = True
                        close_reason = "Take Profit 2 Hit (Target Complete)"
                        final_pnl = ((entry - tp2) / entry) * 100.0
                        new_status = "CLOSED"
                    
                    # 3. Check Take Profit 1
                    elif current_status == "OPEN" and live_price <= tp1:
                        new_status = "TP1_HIT"
                        partial_pnl = ((entry - tp1) / entry) * 100.0
                        # Trailing mechanism: Move SL to Entry
                        sl = entry 
                        
                        cursor.execute("UPDATE signals SET status = 'TP1_HIT', sl = ?, pnl_percent = ? WHERE id = ?", (sl, partial_pnl, pos_id))
                        conn.commit()
                        
                        msg = f"🎯 [TP1 HIT] {symbol} Short reached TP1 at {live_price:.4f}! PnL: +{partial_pnl:.2f}%. Moving SL to Entry ({sl:.4f})."
                        telegram_bot.send_message(msg)
                        closed_reports.append(msg)

                # --- CLOSING LOGIC ---
                if should_close:
                    cursor.execute("""
                        UPDATE signals 
                        SET status = ?, pnl_percent = ?, close_reason = ? 
                        WHERE id = ?
                    """, (new_status, final_pnl, close_reason, pos_id))
                    conn.commit()
                    
                    sign_str = "+" if final_pnl > 0 else ""
                    msg = f"🏁 [POSITION CLOSED] {symbol} {direction}\nReason: {close_reason}\nExit Price: {live_price:.4f}\nFinal PnL: {sign_str}{final_pnl:.2f}%"
                    telegram_bot.send_message(msg)
                    closed_reports.append(msg)
                    
        return closed_reports

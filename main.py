# FILE: src/main.py
# PURPOSE: Main entry point for execution loop, scanning pairs, and orchestrating workflow

import sys
import os
import json
import logging
from concurrent.futures import ThreadPoolExecutor

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.coinex_client import CoinExClient
from src.database import DatabaseManager
from src.telegram_bot import TelegramBot
from src.brain import Brain
from src.strategy import AdvancedMLStrategy

# Setup Logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MainBot")

def process_symbol(symbol: str, client: CoinExClient, db: DatabaseManager, brain: Brain, telegram: TelegramBot, params_dict: dict):
    """Processes a single symbol: fetches data, calculates strategy, and generates signals."""
    try:
        # Avoid checking if we already have an open position for this specific asset
        if db.has_open_position(symbol):
            logger.info(f"Skipping scanning for {symbol}, a position is already active.")
            return

        # Fetch candles
        candles = client.get_last_candles(market=symbol, limit=100, period=config.TIMEFRAME)
        if not candles or len(candles) < 30:
            logger.warning(f"Not enough candles fetched for {symbol}")
            return

        # Load dynamic parameters optimized for this symbol
        symbol_params = params_dict.get(symbol, {})
        
        # Initialize strategy with dynamic/fallback parameters
        strategy = AdvancedMLStrategy(params=symbol_params)
        
        # Execute Strategy Logic (Combines Technical Indicators & ML model prediction)
        signal = strategy.check_signal(candles, brain, symbol)
        
        if signal and signal.get("action") in ["LONG", "SHORT"]:
            action = signal["action"]
            entry = signal["entry"]
            sl = signal["sl"]
            tp1 = signal["tp1"]
            tp2 = signal["tp2"]
            ml_prob = signal.get("probability", 0.0)
            
            # Save to Database (Returns True if newly inserted successfully)
            success = db.save_signal(symbol, action, entry, sl, tp1, tp2)
            
            if success:
                msg = (
                    f"🚀 **NEW ML SIGNAL GENERATED**\n\n"
                    f"🔹 **Asset:** {symbol}\n"
                    f"🔹 **Action:** {action}\n"
                    f"🔹 **Entry Price:** {entry:.4f}\n"
                    f"🛑 **Stop Loss:** {sl:.4f}\n"
                    f"🎯 **Target 1 (Partial):** {tp1:.4f}\n"
                    f"🎯 **Target 2 (Final):** {tp2:.4f}\n"
                    f"🤖 **AI Confidence:** {ml_prob*100:.1f}%"
                )
                telegram.send_message(msg)
                db.log_execution(f"Signal executed for {symbol}: {action}")
                
    except Exception as e:
        logger.error(f"Error processing symbol {symbol}: {e}", exc_info=True)

def main():
    logger.info("Initializing Trading Bot System...")
    
    # Core system components
    client = CoinExClient()
    db = DatabaseManager()
    telegram = TelegramBot()
    brain = Brain()
    
    # 1. FIRST STEP: Track & Manage existing live positions before generating new trades
    logger.info("Step 1: Managing and tracking open positions...")
    db.manage_open_positions(coinex_client=client, telegram_bot=telegram)
    
    # Load dynamic optimization parameters if available
    params_dict = {}
    if os.path.exists(config.PARAMS_FILE):
        try:
            with open(config.PARAMS_FILE, "r") as f:
                params_dict = json.load(f)
            logger.info("Dynamic parameters successfully loaded.")
        except Exception as e:
            logger.error(f"Failed to read parameters file: {e}")

    # 2. SECOND STEP: Scan markets for new opportunities
    logger.info("Step 2: Scanning markets for new setups...")
    symbols_to_scan = config.SYMBOLS
    
    # Multithreading execution for parallel symbol processing
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        for symbol in symbols_to_scan:
            executor.submit(process_symbol, symbol, client, db, brain, telegram, params_dict)
            
    db.log_execution("Cycle executed successfully.")
    logger.info("Bot cycle execution finished.")

if __name__ == "__main__":
    main()

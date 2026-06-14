# FILE: src/strategy.py
# PURPOSE: Core trading strategy logic combining technical indicators with ML models

import pandas as pd
import logging
import config
from src.indicators import calculate_indicators
from src.strategy_utils import find_swings

logger = logging.getLogger(__name__)

class AdvancedMLStrategy:
    def __init__(self, params: dict = None):
        # Default fallback parameters if dynamic optimizer hasn't run yet
        self.params = params or {
            "rsi_period": 14,
            "atr_period": 14,
            "risk_reward_ratio": 2.0
        }

    def check_signal(self, candles: list, brain, symbol: str) -> dict:
        """
        Processes candles, runs technical analysis and ML brain to look for signals.
        """
        df = pd.DataFrame(candles)
        if df.empty or len(df) < 30:
            return {"action": "HOLD"}
            
        # 1. Calculate Sensors & Indicators
        df = calculate_indicators(df)
        
        # Clean infinite or NaN entries that break ML Scalers
        df.replace([return_inf for return_inf in [float('inf'), float('-inf')]], pd.NA, inplace=True)
        df.dropna(inplace=True)
        
        if len(df) < 5:
            return {"action": "HOLD"}
            
        latest_row = df.iloc[-1]
        close_price = float(latest_row["close"])
        
        # 2. Extract technical feature matrix for the ML Brain
        # Dropping non-feature columns
        feature_cols = [col for col in df.columns if col not in ["timestamp", "open", "high", "low", "close", "volume", "target"]]
        features_df = df[feature_cols]
        
        # 3. Request prediction from Brain
        prediction, probability = brain.predict_direction(symbol, features_df)
        
        # 4. Find structural Swings for Risk Management (SL / TP)
        swings = find_swings(df)
        last_swing_high = swings.get("last_high", close_price * 1.02)
        last_swing_low = swings.get("last_low", close_price * 0.98)
        
        # Basic ATR for dynamic buffer
        atr = float(latest_row.get("atr", close_price * 0.01))
        rr = self.params.get("risk_reward_ratio", 2.0)
        
        # 5. Signal generation matching ML predictions
        # Assuming Model Target: 1 = Price Up (LONG), 2 = Price Down (SHORT), 0 = HOLD
        if prediction == 1 and probability >= config.PROBABILITY_THRESHOLD:
            sl = min(last_swing_low, close_price - (1.5 * atr))
            if sl >= close_price: 
                sl = close_price - (2 * atr)
                
            risk = close_price - sl
            tp1 = close_price + (risk * 1.0) # Partial profit at 1:1 RR
            tp2 = close_price + (risk * rr)  # Final profit target
            
            return {
                "action": "LONG",
                "entry": close_price,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "probability": probability
            }
            
        elif prediction == 2 and probability >= config.PROBABILITY_THRESHOLD:
            sl = max(last_swing_high, close_price + (1.5 * atr))
            if sl <= close_price: 
                sl = close_price + (2 * atr)
                
            risk = sl - close_price
            tp1 = close_price - (risk * 1.0)
            tp2 = close_price - (risk * rr)
            
            return {
                "action": "SHORT",
                "entry": close_price,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "probability": probability
            }
            
        return {"action": "HOLD"}

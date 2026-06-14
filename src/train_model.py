# FILE: src/train_model.py
# PURPOSE: Full ML training pipeline using LightGBM with time-series protection

import os
import json
import logging
import sqlite3
import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb  # Imported LightGBM

import config
from src.indicators import calculate_indicators

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TrainModel_LightGBM")

def load_data_from_db(symbol: str) -> pd.DataFrame:
    """Loads history candles from local DB for a specific symbol."""
    db_path = os.path.join("data", f"{symbol}_history.db")
    if not os.path.exists(db_path):
        db_path = config.DB_PATH_LIVE  # fallback to shared DB
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='candles_{symbol}'")
        if not cursor.fetchone():
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='candles'")
            table_name = "candles" if cursor.fetchone() else None
        else:
            table_name = f"candles_{symbol}"
            
        if not table_name:
            logger.warning(f"No candle table found for {symbol} in {db_path}")
            return pd.DataFrame()
            
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error loading data from DB for {symbol}: {e}")
        return pd.DataFrame()

def prepare_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates indicators and creates the classification target."""
    if df.empty or len(df) < 50:
        return pd.DataFrame()
        
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)
        
    # Calculate all sensors/indicators
    df = calculate_indicators(df)
    
    # Create target: 1 if close price goes UP, 2 if DOWN, 0 if flat
    df['future_close'] = df['close'].shift(-1)
    
    conditions = [
        (df['future_close'] > df['close'] * 1.001), # UP
        (df['future_close'] < df['close'] * 0.999)  # DOWN
    ]
    choices = [1, 2]
    df['target'] = np.select(conditions, choices, default=0)
    
    df.replace([float('inf'), float('-inf')], np.nan, inplace=True)
    df.dropna(inplace=True)
    
    return df

def train_model_for_symbol(symbol: str):
    """Executes the training pipeline using LightGBM Classifier."""
    logger.info(f"--- Starting LightGBM Training Pipeline for {symbol} ---")
    
    raw_df = load_data_from_db(symbol)
    if raw_df.empty:
        logger.warning(f"Skipping {symbol}: No data found.")
        return
        
    df = prepare_dataset(raw_df)
    if df.empty or len(df) < 100:
        logger.warning(f"Skipping {symbol}: Not enough processed data rows ({len(df)}).")
        return
        
    # Exclude non-feature columns
    exclude_cols = ["timestamp", "open", "high", "low", "close", "volume", "future_close", "target"]
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    
    X = df[feature_cols]
    y = df["target"].astype(int)
    
    # Time-Series Split (80% train, 20% test) to prevent data leakage
    split_idx = int(len(df) * 0.8)
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    logger.info(f"Dataset Split -> Train size: {len(X_train)}, Test size: {len(X_test)}")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # --- LIGHTGBM CLASSIFIER INITIALIZATION ---
    # Optimized hyper-parameters for financial time-series prediction
    model = lgb.LGBMClassifier(
        n_estimators=150,
        learning_rate=0.03,
        max_depth=6,
        num_leaves=31,
        random_state=42,
        objective='multiclass',   # 3 classes: 0, 1, 2
        num_class=3,
        class_weight='balanced',  # Automatically handles unbalance in market conditions
        n_jobs=-1,                 # Use all CPU cores
        verbose=-1                # Suppress unnecessary logs
    )
    
    # Train the LightGBM model
    model.fit(
        X_train_scaled, 
        y_train,
        eval_set=[(X_test_scaled, y_test)],
        callbacks=[lgb.early_stopping(stopping_rounds=15, verbose=False)]
    )
    
    # Evaluation
    train_acc = model.score(X_train_scaled, y_train)
    test_acc = model.score(X_test_scaled, y_test)
    logger.info(f"LightGBM Results for {symbol} -> Train Acc: {train_acc*100:.2f}%, Test Acc: {test_acc*100:.2f}%")
    
    # --- SAVE MODEL COMPONENTS ---
    os.makedirs(config.MODELS_DIR, exist_ok=True)
    
    model_path = os.path.join(config.MODELS_DIR, f"{symbol}_model.pkl")
    scaler_path = os.path.join(config.MODELS_DIR, f"{symbol}_scaler.pkl")
    
    # joblib saves LightGBM models perfectly
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    
    # Save feature names mapping for live execution alignment
    features_json_path = os.path.join(config.MODELS_DIR, f"{symbol}_features.json")
    with open(features_json_path, "w") as f:
        json.dump(feature_cols, f, indent=4)
        
    logger.info(f"Successfully saved LightGBM components for {symbol}.")

def main():
    symbols = config.SYMBOLS
    for symbol in symbols:
        try:
            train_model_for_symbol(symbol)
        except Exception as e:
            logger.error(f"Failed LightGBM pipeline for {symbol}: {e}", exc_info=True)

if __name__ == "__main__":
    main()

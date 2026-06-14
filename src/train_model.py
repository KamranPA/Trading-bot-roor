# FILE: src/train_model.py
# PURPOSE: High-stability LightGBM training pipeline with strict feature columns extraction

import os
import json
import logging
import sqlite3
import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb

import config
from src.indicators import calculate_indicators

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TrainModel_LightGBM_Final")

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
    if df.empty or len(df) < 30:
        return pd.DataFrame()
        
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)
        
    # Calculate indicators
    df = calculate_indicators(df)
    
    # Create target: 1 if close price goes UP, 2 if DOWN, 0 if flat
    df['future_close'] = df['close'].shift(-1)
    
    conditions = [
        (df['future_close'] > df['close'] * 1.0005), # UP
        (df['future_close'] < df['close'] * 0.9995)  # DOWN
    ]
    choices = [1, 2]
    df['target'] = np.select(conditions, choices, default=0)
    
    df.replace([float('inf'), float('-inf')], np.nan, inplace=True)
    df.dropna(inplace=True)
    
    return df

def train_model_for_symbol(symbol: str):
    """Executes the training pipeline using LightGBM with strict clean features isolation."""
    logger.info(f"--- Starting Final LightGBM Pipeline for {symbol} ---")
    
    raw_df = load_data_from_db(symbol)
    if raw_df.empty:
        logger.warning(f"Skipping {symbol}: Database table is empty.")
        return
        
    df = prepare_dataset(raw_df)
    total_rows = len(df)
    if df.empty or total_rows < 40:
        logger.warning(f"Skipping {symbol}: Insufficient historical rows ({total_rows}).")
        return
        
    # 1. STRICT SEPARATION OF TARGET AND FEATURES
    y = df["target"].astype(int).copy()
    
    # Define columns that MUST NEVER be fed into the training matrix X
    exclude_cols = ["timestamp", "open", "high", "low", "close", "volume", "future_close", "target"]
    
    # Keep ONLY numerical indicator columns that are not in the forbidden list
    feature_cols = []
    for col in df.columns:
        if col not in exclude_cols:
            # Check if column is numeric to avoid LightGBM object/string errors
            if pd.api.types.is_numeric_dtype(df[col]):
                feature_cols.append(col)
    
    # Explicitly slice X to contain only safe feature columns
    X = df[feature_cols].copy()
    
    # 2. SAFE TIME-SERIES SPLIT
    test_size = max(15, int(total_rows * 0.15))
    split_idx = total_rows - test_size
    
    if split_idx < 20:
        split_idx = int(total_rows * 0.8)
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    logger.info(f"Dataset Verified -> Train size: {len(X_train)}, Test size: {len(X_test)}, Total Features: {len(feature_cols)}")
    
    # 3. SCALE FEATURES
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 4. LIGHTGBM MODEL DEFINITION
    model = lgb.LGBMClassifier(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=4,
        num_leaves=15,
        min_child_samples=2,
        random_state=42,
        objective='multiclass',
        num_class=3,
        class_weight='balanced',
        n_jobs=-1,
        verbose=-1
    )
    
    callbacks = []
    if len(X_test_scaled) >= 10:
        callbacks.append(lgb.early_stopping(stopping_rounds=5, verbose=False))
        
    # Fit the model securely using aligned numpy arrays
    model.fit(
        X_train_scaled, 
        y_train,
        eval_set=[(X_test_scaled, y_test)],
        callbacks=callbacks
    )
    
    # Evaluation
    train_acc = model.score(X_train_scaled, y_train)
    test_acc = model.score(X_test_scaled, y_test)
    logger.info(f"Results for {symbol} -> Train Acc: {train_acc*100:.2f}%, Test Acc: {test_acc*100:.2f}%")
    
    # 5. SAVE COMPONENTS
    os.makedirs(config.MODELS_DIR, exist_ok=True)
    
    model_path = os.path.join(config.MODELS_DIR, f"{symbol}_model.pkl")
    scaler_path = os.path.join(config.MODELS_DIR, f"{symbol}_scaler.pkl")
    
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    
    features_json_path = os.path.join(config.MODELS_DIR, f"{symbol}_features.json")
    with open(features_json_path, "w") as f:
        json.dump(feature_cols, f, indent=4)
        
    logger.info(f"Successfully saved clean LightGBM components for {symbol}.")

def main():
    symbols = config.SYMBOLS
    for symbol in symbols:
        try:
            train_model_for_symbol(symbol)
        except Exception as e:
            logger.error(f"Failed LightGBM pipeline for {symbol}: {e}", exc_info=True)

if __name__ == "__main__":
    main()

# FILE: src/train_model.py
# PURPOSE: Bulletproof LightGBM training pipeline with strict class & feature guards

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
logger = logging.getLogger("TrainModel_Bulletproof")

def load_data_from_db(symbol: str) -> pd.DataFrame:
    db_path = os.path.join("data", f"{symbol}_history.db")
    if not os.path.exists(db_path):
        db_path = config.DB_PATH_LIVE  
        
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
            logger.warning(f"No table found for {symbol}")
            return pd.DataFrame()
            
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error loading DB for {symbol}: {e}")
        return pd.DataFrame()

def prepare_dataset(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 30:
        return pd.DataFrame()
        
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)
        
    df = calculate_indicators(df)
    
    df['future_close'] = df['close'].shift(-1)
    
    conditions = [
        (df['future_close'] > df['close'] * 1.0005), # UP (1)
        (df['future_close'] < df['close'] * 0.9995)  # DOWN (2)
    ]
    choices = [1, 2]
    df['target'] = np.select(conditions, choices, default=0) # FLAT (0)
    
    df.replace([float('inf'), float('-inf')], np.nan, inplace=True)
    df.dropna(inplace=True)
    
    return df

def train_model_for_symbol(symbol: str):
    logger.info(f"--- Starting Bulletproof Pipeline for {symbol} ---")
    
    raw_df = load_data_from_db(symbol)
    if raw_df.empty:
        logger.warning(f"Skipping {symbol}: Database is empty.")
        return
        
    df = prepare_dataset(raw_df)
    total_rows = len(df)
    if df.empty or total_rows < 40:
        logger.warning(f"Skipping {symbol}: Insufficient rows ({total_rows}).")
        return
        
    y = df["target"].astype(int).copy()
    
    exclude_cols = ["timestamp", "open", "high", "low", "close", "volume", "future_close", "target"]
    feature_cols = [col for col in df.columns if col not in exclude_cols and pd.api.types.is_numeric_dtype(df[col])]
    
    X = df[feature_cols].copy()
    
    test_size = max(15, int(total_rows * 0.15))
    split_idx = total_rows - test_size
    
    if split_idx < 20:
        split_idx = int(total_rows * 0.8)
    
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # --- 🛡️ THE ULTIMATE FAILSAFE FOR CLASS DIVERSITY ---
    train_classes = np.unique(y_train)
    if len(train_classes) < 2:
        logger.warning(f"Skipping {symbol}: Training data has only ONE class {train_classes}. AI needs at least 2 distinct directions to learn. Feed it more history!")
        return
        
    logger.info(f"Dataset Verified -> Train size: {len(X_train)}, Features: {len(feature_cols)}, Classes: {train_classes}")
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
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
    
    # Disable early stopping if testing data doesn't have enough class diversity
    callbacks = []
    if len(X_test_scaled) >= 10 and len(np.unique(y_test)) >= 2:
        callbacks.append(lgb.early_stopping(stopping_rounds=5, verbose=False))
        
    model.fit(
        X_train_scaled, 
        y_train,
        eval_set=[(X_test_scaled, y_test)],
        callbacks=callbacks
    )
    
    train_acc = model.score(X_train_scaled, y_train)
    test_acc = model.score(X_test_scaled, y_test)
    logger.info(f"Results for {symbol} -> Train Acc: {train_acc*100:.2f}%, Test Acc: {test_acc*100:.2f}%")
    
    os.makedirs(config.MODELS_DIR, exist_ok=True)
    
    model_path = os.path.join(config.MODELS_DIR, f"{symbol}_model.pkl")
    scaler_path = os.path.join(config.MODELS_DIR, f"{symbol}_scaler.pkl")
    
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    
    features_json_path = os.path.join(config.MODELS_DIR, f"{symbol}_features.json")
    with open(features_json_path, "w") as f:
        json.dump(feature_cols, f, indent=4)
        
    logger.info(f"Successfully saved AI components for {symbol}.")

def main():
    symbols = config.SYMBOLS
    for symbol in symbols:
        try:
            train_model_for_symbol(symbol)
        except Exception as e:
            logger.error(f"Failed pipeline for {symbol}: {e}", exc_info=True)

if __name__ == "__main__":
    main()

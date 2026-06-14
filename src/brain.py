# FILE: src/brain.py
# PURPOSE: Loads ML models and safely handles inference/predictions without shape errors

import os
import joblib
import logging
import pandas as pd
import config

logger = logging.getLogger(__name__)

class Brain:
    def __init__(self):
        self.models_dir = config.MODELS_DIR
        self.scaler_dir = config.MODELS_DIR
        
    def _get_model_paths(self, symbol: str):
        model_path = os.path.join(self.models_dir, f"{symbol}_model.pkl")
        scaler_path = os.path.join(self.scaler_dir, f"{symbol}_scaler.pkl")
        features_path = os.path.join(self.scaler_dir, f"{symbol}_features.json")
        return model_path, scaler_path, features_path

    def predict_direction(self, symbol: str, features_df: pd.DataFrame) -> tuple:
        """
        Predicts the market direction for a given symbol using saved models.
        Returns (prediction_code, probability) or (0, 0.0) if failed.
        """
        model_path, scaler_path, _ = self._get_model_paths(symbol)
        
        if not os.path.exists(model_path) or not os.path.exists(scaler_path):
            logger.warning(f"No ML model found for {symbol}. Skipping AI prediction.")
            return 0, 0.0
            
        try:
            # Load models
            model = joblib.load(model_path)
            scaler = joblib.load(scaler_path)
            
            # Align features to ensure exact same column order and shapes as training
            # Extract only the last row for inference
            latest_features = features_df.iloc[[-1]].copy()
            
            # Handle expected features by checking model attributes if available
            if hasattr(model, "feature_names_in_"):
                expected_features = model.feature_names_in_
                # Reindex columns to match training exactly, filling missing with 0
                latest_features = latest_features.reindex(columns=expected_features, fill_value=0)
            elif hasattr(scaler, "feature_names_in_"):
                expected_features = scaler.feature_names_in_
                latest_features = latest_features.reindex(columns=expected_features, fill_value=0)
            
            # Scale features
            scaled_data = scaler.transform(latest_features)
            
            # Predict
            prediction = model.predict(scaled_data)[0]
            
            # Get probability
            probability = 0.5
            if hasattr(model, "predict_proba"):
                prob_idx = model.predict_proba(scaled_data)[0]
                probability = max(prob_idx)
                
            return int(prediction), float(probability)
            
        except Exception as e:
            logger.error(f"Prediction failed for {symbol}: {e}", exc_info=True)
            return 0, 0.0

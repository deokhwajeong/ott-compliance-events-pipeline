"""
Deep Learning Models Module
Implements LSTM and Transformer models for advanced anomaly detection
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import logging
from typing import Tuple, List, Dict, Any
from datetime import datetime
import pickle
import os

logger = logging.getLogger(__name__)


class LSTMModel:
    """LSTM model for time-series anomaly detection"""

    def __init__(
        self,
        sequence_length: int = 24,
        n_features: int = 10,
        lstm_units: int = 64,
        dropout_rate: float = 0.2,
    ):
        self.sequence_length = sequence_length
        self.n_features = n_features
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.model = self._build_model()
        self.scaler_mean = None
        self.scaler_std = None

    def _build_model(self) -> keras.Model:
        """Build LSTM model architecture"""
        model = keras.Sequential(
            [
                layers.Input(shape=(self.sequence_length, self.n_features)),
                layers.LSTM(
                    self.lstm_units, activation="relu", return_sequences=True
                ),
                layers.Dropout(self.dropout_rate),
                layers.LSTM(self.lstm_units // 2, activation="relu"),
                layers.Dropout(self.dropout_rate),
                layers.Dense(32, activation="relu"),
                layers.Dense(self.n_features),  # Reconstruction
            ]
        )

        model.compile(optimizer="adam", loss="mse", metrics=["mae"])
        return model

    def normalize(self, data: np.ndarray) -> np.ndarray:
        """Normalize input data"""
        if self.scaler_mean is None:
            self.scaler_mean = np.mean(data, axis=0)
            self.scaler_std = np.std(data, axis=0)
        return (data - self.scaler_mean) / (self.scaler_std + 1e-8)

    def denormalize(self, data: np.ndarray) -> np.ndarray:
        """Denormalize data"""
        if self.scaler_mean is None:
            return data
        return data * (self.scaler_std + 1e-8) + self.scaler_mean

    def create_sequences(
        self, data: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Create sequences for LSTM training"""
        X, y = [], []
        for i in range(len(data) - self.sequence_length):
            X.append(data[i : i + self.sequence_length])
            y.append(data[i + self.sequence_length])
        return np.array(X), np.array(y)

    def train(
        self,
        data: np.ndarray,
        epochs: int = 50,
        batch_size: int = 32,
        validation_split: float = 0.2,
    ) -> Dict[str, List[float]]:
        """Train LSTM model on normal data"""
        # Normalize data
        normalized_data = self.normalize(data)

        # Create sequences
        X, y = self.create_sequences(normalized_data)

        # Train model
        history = self.model.fit(
            X,
            y,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            verbose=0,
            shuffle=True,
        )

        logger.info(f"LSTM training completed. Final loss: {history.history['loss'][-1]:.4f}")
        return history.history

    def detect_anomalies(
        self, data: np.ndarray, threshold_percentile: float = 95
    ) -> Tuple[List[bool], np.ndarray]:
        """Detect anomalies using reconstruction error"""
        normalized_data = self.normalize(data)
        X, _ = self.create_sequences(normalized_data)

        # Get predictions
        predictions = self.model.predict(X, verbose=0)

        # Calculate reconstruction error
        reconstruction_errors = np.mean(np.abs(predictions - X[:, -1, :]), axis=1)

        # Determine threshold
        threshold = np.percentile(reconstruction_errors, threshold_percentile)

        # Detect anomalies
        anomalies = reconstruction_errors > threshold

        return anomalies.tolist(), reconstruction_errors

    def save(self, path: str):
        """Save model to disk"""
        self.model.save(os.path.join(path, "lstm_model.h5"))
        params = {
            "sequence_length": self.sequence_length,
            "n_features": self.n_features,
            "lstm_units": self.lstm_units,
            "dropout_rate": self.dropout_rate,
            "scaler_mean": self.scaler_mean,
            "scaler_std": self.scaler_std,
        }
        with open(os.path.join(path, "lstm_params.pkl"), "wb") as f:
            pickle.dump(params, f)
        logger.info(f"LSTM model saved to {path}")

    @classmethod
    def load(cls, path: str) -> "LSTMModel":
        """Load model from disk"""
        with open(os.path.join(path, "lstm_params.pkl"), "rb") as f:
            params = pickle.load(f)

        instance = cls(
            sequence_length=params["sequence_length"],
            n_features=params["n_features"],
            lstm_units=params["lstm_units"],
            dropout_rate=params["dropout_rate"],
        )
        instance.model = keras.models.load_model(os.path.join(path, "lstm_model.h5"))
        instance.scaler_mean = params["scaler_mean"]
        instance.scaler_std = params["scaler_std"]
        return instance


class TransformerModel:
    """Transformer model for sequence analysis and anomaly detection"""

    def __init__(
        self,
        sequence_length: int = 24,
        n_features: int = 10,
        d_model: int = 64,
        n_heads: int = 4,
        n_layers: int = 2,
        dff: int = 128,
    ):
        self.sequence_length = sequence_length
        self.n_features = n_features
        self.d_model = d_model
        self.n_heads = n_heads
        self.n_layers = n_layers
        self.dff = dff
        self.model = self._build_model()

    def _build_model(self) -> keras.Model:
        """Build Transformer model architecture"""
        inputs = keras.Input(shape=(self.sequence_length, self.n_features))

        # Linear projection to d_model dimensions
        x = layers.Dense(self.d_model)(inputs)

        # Transformer encoder layers
        for _ in range(self.n_layers):
            # Multi-head attention
            attention = layers.MultiHeadAttention(
                num_heads=self.n_heads, key_dim=self.d_model // self.n_heads
            )(x, x)
            x = layers.Add()([x, attention])
            x = layers.LayerNormalization()(x)

            # Feed-forward network
            ffn = keras.Sequential(
                [layers.Dense(self.dff, activation="relu"), layers.Dense(self.d_model)]
            )(x)
            x = layers.Add()([x, ffn])
            x = layers.LayerNormalization()(x)

        # Global average pooling and output
        x = layers.GlobalAveragePooling1D()(x)
        outputs = layers.Dense(self.n_features)(x)

        model = keras.Model(inputs=inputs, outputs=outputs)
        model.compile(optimizer="adam", loss="mse")
        return model

    def train(
        self,
        X_train: np.ndarray,
        X_val: np.ndarray,
        epochs: int = 50,
        batch_size: int = 32,
    ) -> Dict[str, List[float]]:
        """Train Transformer model"""
        history = self.model.fit(
            X_train,
            X_train,
            validation_data=(X_val, X_val),
            epochs=epochs,
            batch_size=batch_size,
            verbose=0,
        )
        logger.info(f"Transformer training completed. Final loss: {history.history['loss'][-1]:.4f}")
        return history.history


class EnsembleDeepLearning:
    """Ensemble of LSTM and Transformer models"""

    def __init__(self):
        self.lstm_model = None
        self.transformer_model = None
        self.ensemble_weights = {"lstm": 0.6, "transformer": 0.4}

    def initialize_models(
        self, sequence_length: int = 24, n_features: int = 10
    ):
        """Initialize both models"""
        self.lstm_model = LSTMModel(
            sequence_length=sequence_length, n_features=n_features
        )
        self.transformer_model = TransformerModel(
            sequence_length=sequence_length, n_features=n_features
        )

    def train_ensemble(
        self, training_data: np.ndarray, epochs: int = 50
    ):
        """Train both models in ensemble"""
        logger.info("Training ensemble models...")

        # Train LSTM
        self.lstm_model.train(training_data, epochs=epochs)

        # Prepare data for Transformer
        normalized_data = self.lstm_model.normalize(training_data)
        X, y = self.lstm_model.create_sequences(normalized_data)
        split_idx = int(0.8 * len(X))

        self.transformer_model.train(
            X[:split_idx], X[split_idx:], epochs=epochs
        )

        logger.info("Ensemble training completed")

    def detect_anomalies(
        self, data: np.ndarray, threshold_percentile: float = 95
    ) -> Tuple[List[bool], Dict[str, Any]]:
        """Detect anomalies using ensemble voting"""
        if not self.lstm_model or not self.transformer_model:
            raise ValueError("Models not initialized")

        # LSTM anomaly detection
        lstm_anomalies, lstm_errors = self.lstm_model.detect_anomalies(
            data, threshold_percentile
        )

        # Transformer reconstruction
        normalized_data = self.lstm_model.normalize(data)
        X, _ = self.lstm_model.create_sequences(normalized_data)
        predictions = self.transformer_model.model.predict(X, verbose=0)
        transformer_errors = np.mean(np.abs(predictions - X[:, -1, :]), axis=1)
        transformer_threshold = np.percentile(transformer_errors, threshold_percentile)
        transformer_anomalies = (transformer_errors > transformer_threshold).tolist()

        # Ensemble decision
        ensemble_scores = [
            self.ensemble_weights["lstm"] * (1 if lstm else 0)
            + self.ensemble_weights["transformer"] * (1 if trans else 0)
            for lstm, trans in zip(lstm_anomalies, transformer_anomalies)
        ]
        ensemble_anomalies = [score >= 0.5 for score in ensemble_scores]

        return ensemble_anomalies, {
            "lstm_errors": lstm_errors.tolist(),
            "transformer_errors": transformer_errors.tolist(),
            "ensemble_scores": ensemble_scores,
            "timestamp": datetime.utcnow().isoformat(),
        }

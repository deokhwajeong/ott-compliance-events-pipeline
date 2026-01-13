"""Enhanced ML models for anomaly detection and violation prediction"""

import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Any, Tuple
import joblib
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)


class EnhancedAnomalyDetector:
    """Advanced ML-based anomaly detection with multiple algorithms"""
    
    def __init__(self):
        self.isolation_forest = None
        self.lof = None
        self.scaler = StandardScaler()
        self.feature_history = []
        self.max_history = 10000
        self.model_path = MODEL_DIR / "anomaly_detector.pkl"
        self.load_models()
    
    def extract_features(self, event: Dict) -> np.ndarray:
        """Extract numerical features from event for ML processing"""
        features = []
        
        # Time-based features
        try:
            timestamp = datetime.fromisoformat(event.get("timestamp", "").replace('Z', '+00:00'))
            features.append(timestamp.hour)  # Hour of day (0-23)
            features.append(timestamp.weekday())  # Day of week (0-6)
        except:
            features.extend([12, 3])  # Default values
        
        # Count features (normalized)
        features.append(len(str(event.get("event_type", ""))))  # Event type length
        features.append(1 if event.get("error_code") else 0)  # Has error
        features.append(1 if event.get("is_eu") else 0)  # EU region
        features.append(1 if event.get("has_consent") else 0)  # Has consent
        
        # Categorical features (encoded)
        subscription_map = {"basic": 0, "premium": 1, "vip": 2}
        features.append(subscription_map.get(event.get("subscription_plan"), 0))
        
        # Event type encoding
        event_type_map = {
            "play": 1, "pause": 2, "stop": 3, "seek": 4,
            "login": 5, "logout": 6, "login_failed": 7,
            "purchase": 8, "download": 9, "error": 10
        }
        features.append(event_type_map.get(event.get("event_type", ""), 0))
        
        return np.array(features, dtype=float)
    
    def detect_anomaly_isolation_forest(
        self,
        event: Dict,
        contamination: float = 0.1
    ) -> Tuple[bool, float]:
        """
        Use Isolation Forest for anomaly detection.
        Better at detecting outliers than Z-score.
        """
        try:
            features = self.extract_features(event)
            features = features.reshape(1, -1)
            
            # Initialize if not exists
            if self.isolation_forest is None:
                self.isolation_forest = IsolationForest(
                    contamination=contamination,
                    random_state=42,
                    n_estimators=100
                )
                # Fit on feature itself (will improve with more data)
                self.isolation_forest.fit(features)
            
            # Predict (-1 = anomaly, 1 = normal)
            prediction = self.isolation_forest.predict(features)[0]
            anomaly_score = -self.isolation_forest.score_samples(features)[0]
            
            is_anomaly = prediction == -1
            
            logger.debug(f"Isolation Forest: anomaly={is_anomaly}, score={anomaly_score:.3f}")
            
            return is_anomaly, float(anomaly_score)
            
        except Exception as e:
            logger.error(f"Isolation Forest error: {e}")
            return False, 0.0
    
    def detect_anomaly_lof(
        self,
        event: Dict,
        n_neighbors: int = 20
    ) -> Tuple[bool, float]:
        """
        Use Local Outlier Factor for detecting local anomalies.
        Good at detecting cluster anomalies.
        """
        try:
            if len(self.feature_history) < n_neighbors + 1:
                return False, 0.0
            
            features = self.extract_features(event)
            
            # Combine historical features with current event
            X = np.vstack([self.feature_history[-n_neighbors:], features.reshape(1, -1)])
            
            lof = LocalOutlierFactor(n_neighbors=n_neighbors)
            lof.fit(X)
            
            # Check if latest point (current event) is anomaly
            lof_scores = lof.negative_outlier_factor_
            current_score = lof_scores[-1]
            
            is_anomaly = current_score < np.mean(lof_scores) - 2 * np.std(lof_scores)
            
            logger.debug(f"LOF: anomaly={is_anomaly}, score={current_score:.3f}")
            
            return is_anomaly, float(abs(current_score))
            
        except Exception as e:
            logger.error(f"LOF error: {e}")
            return False, 0.0
    
    def ensemble_anomaly_detection(
        self,
        event: Dict
    ) -> Dict[str, Any]:
        """
        Combine multiple algorithms for robust detection.
        Returns consensus result.
        """
        if_anomaly, if_score = self.detect_anomaly_isolation_forest(event)
        lof_anomaly, lof_score = self.detect_anomaly_lof(event)
        
        # Ensemble: majority vote + average score
        anomaly_votes = sum([if_anomaly, lof_anomaly])
        is_ensemble_anomaly = anomaly_votes >= 1  # At least 1 algorithm says anomaly
        
        ensemble_score = (if_score + lof_score) / 2
        
        flags = []
        if if_anomaly:
            flags.append("isolation_forest_anomaly")
        if lof_anomaly:
            flags.append("lof_anomaly")
        
        result = {
            "is_anomaly": is_ensemble_anomaly,
            "ensemble_score": ensemble_score,
            "flags": flags,
            "isolation_forest": {
                "is_anomaly": if_anomaly,
                "score": if_score
            },
            "lof": {
                "is_anomaly": lof_anomaly,
                "score": lof_score
            }
        }
        
        # Store features for future learning
        self._add_to_history(self.extract_features(event))
        
        return result
    
    def _add_to_history(self, features: np.ndarray) -> None:
        """Add features to historical data for model learning"""
        self.feature_history.append(features)
        
        if len(self.feature_history) > self.max_history:
            self.feature_history = self.feature_history[-self.max_history:]
    
    def retrain_models(self, force: bool = False) -> bool:
        """Retrain models with accumulated feature history"""
        try:
            if len(self.feature_history) < 100 and not force:
                logger.info("Not enough data to retrain (need 100+ samples)")
                return False
            
            X = np.array(self.feature_history)
            
            # Retrain Isolation Forest
            self.isolation_forest = IsolationForest(
                contamination=0.1,
                random_state=42,
                n_estimators=100
            )
            self.isolation_forest.fit(X)
            
            # Save models
            self.save_models()
            
            logger.info(f"Models retrained with {len(X)} samples")
            return True
            
        except Exception as e:
            logger.error(f"Model retraining error: {e}")
            return False
    
    def save_models(self) -> None:
        """Save trained models to disk"""
        try:
            joblib.dump(self.isolation_forest, MODEL_DIR / "isolation_forest.pkl")
            logger.info("Models saved successfully")
        except Exception as e:
            logger.error(f"Failed to save models: {e}")
    
    def load_models(self) -> None:
        """Load pretrained models from disk"""
        try:
            if (MODEL_DIR / "isolation_forest.pkl").exists():
                self.isolation_forest = joblib.load(MODEL_DIR / "isolation_forest.pkl")
                logger.info("Models loaded from disk")
        except Exception as e:
            logger.warning(f"Could not load models: {e}")


class ViolationPredictor:
    """Predict likelihood of compliance violations"""
    
    def __init__(self):
        self.violation_patterns = {}  # Store violation patterns for learning
        self.model_path = MODEL_DIR / "violation_predictor.pkl"
        self.load_model()
    
    def predict_violation_likelihood(
        self,
        user_history: List[Dict],
        current_event: Dict
    ) -> Dict[str, Any]:
        """
        Predict probability of compliance violation based on history and patterns.
        Uses pattern matching + statistical analysis.
        """
        violation_score = 0.0
        risk_factors = []
        
        if not user_history:
            return {
                "violation_likelihood": 0.0,
                "risk_factors": [],
                "predicted_regulations": []
            }
        
        recent_events = user_history[-50:] if len(user_history) > 50 else user_history
        
        # Factor 1: Consent pattern changes
        recent_consent = [e.get("has_consent", True) for e in recent_events[-10:]]
        if recent_consent.count(False) > 5:
            violation_score += 0.3
            risk_factors.append("frequent_no_consent")
        
        # Factor 2: EU region + no consent
        eu_no_consent_count = sum(
            1 for e in recent_events 
            if e.get("is_eu") and not e.get("has_consent")
        )
        if eu_no_consent_count > 2:
            violation_score += 0.4
            risk_factors.append("gdpr_violation_pattern")
        
        # Factor 3: Data access patterns (potential California violation)
        data_access_events = [
            e for e in recent_events 
            if e.get("event_type") in {"export", "download", "access"}
        ]
        if len(data_access_events) > 10:
            violation_score += 0.2
            risk_factors.append("high_data_access_frequency")
        
        # Factor 4: Failed auth attempts (potential account compromise)
        failed_auth = sum(
            1 for e in recent_events 
            if e.get("event_type") in {"login_failed", "token_refresh_failed"}
        )
        if failed_auth > 5:
            violation_score += 0.1
            risk_factors.append("repeated_auth_failures")
        
        # Predicted regulations at risk
        predicted_regulations = []
        if "gdpr_violation_pattern" in risk_factors:
            predicted_regulations.append(("GDPR", 0.9))
        if "high_data_access_frequency" in risk_factors:
            predicted_regulations.append(("CCPA", 0.7))
        if "repeated_auth_failures" in risk_factors:
            predicted_regulations.append(("Account Security", 0.8))
        
        return {
            "violation_likelihood": min(violation_score, 1.0),
            "risk_factors": risk_factors,
            "predicted_regulations": predicted_regulations,
            "confidence": min(len(recent_events) / 100, 1.0)  # Confidence based on sample size
        }
    
    def save_model(self) -> None:
        """Save violation patterns to disk"""
        try:
            joblib.dump(self.violation_patterns, self.model_path)
        except Exception as e:
            logger.error(f"Failed to save violation predictor: {e}")
    
    def load_model(self) -> None:
        """Load violation patterns from disk"""
        try:
            if self.model_path.exists():
                self.violation_patterns = joblib.load(self.model_path)
        except Exception as e:
            logger.warning(f"Could not load violation predictor: {e}")


# Global instances
anomaly_detector = EnhancedAnomalyDetector()
violation_predictor = ViolationPredictor()

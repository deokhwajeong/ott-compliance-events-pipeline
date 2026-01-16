"""Advanced Deep Learning Models for OTT Compliance Detection"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any
import logging
from pathlib import Path
from datetime import datetime
import pickle

logger = logging.getLogger(__name__)

MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)


class AdvancedMLEnsemble:
    """Advanced ensemble learning with multiple ML algorithms"""
    
    def __init__(self):
        self.models = {}
        self.scaler = None
        self.feature_names = None
        self.threshold_optimal = 0.65
        
    def train_gradient_boosting(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict:
        """Train XGBoost model for compliance violation prediction"""
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            
            model = GradientBoostingClassifier(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=7,
                min_samples_split=10,
                min_samples_leaf=5,
                subsample=0.8,
                random_state=42,
                validation_fraction=0.1,
                n_iter_no_change=50
            )
            
            model.fit(X_train, y_train)
            self.models['gradient_boosting'] = model
            
            score = model.score(X_train, y_train)
            logger.info(f"Gradient Boosting trained - Accuracy: {score:.4f}")
            
            return {
                'model': 'gradient_boosting',
                'accuracy': score,
                'feature_importance': model.feature_importances_
            }
        except ImportError:
            logger.warning("sklearn Gradient Boosting not available")
            return None
    
    def train_neural_network(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict:
        """Train neural network for deep learning-based detection"""
        try:
            from sklearn.neural_network import MLPClassifier
            
            model = MLPClassifier(
                hidden_layer_sizes=(256, 128, 64),
                activation='relu',
                solver='adam',
                batch_size=32,
                learning_rate='adaptive',
                learning_rate_init=0.001,
                max_iter=500,
                early_stopping=True,
                validation_fraction=0.1,
                random_state=42
            )
            
            model.fit(X_train, y_train)
            self.models['neural_network'] = model
            
            score = model.score(X_train, y_train)
            logger.info(f"Neural Network trained - Accuracy: {score:.4f}")
            
            return {
                'model': 'neural_network',
                'accuracy': score,
                'layers': model.hidden_layer_sizes
            }
        except ImportError:
            logger.warning("sklearn Neural Network not available")
            return None
    
    def train_svm(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict:
        """Train Support Vector Machine for complex boundary detection"""
        try:
            from sklearn.svm import SVC
            
            model = SVC(
                kernel='rbf',
                C=1.0,
                gamma='scale',
                probability=True,
                random_state=42,
                class_weight='balanced'
            )
            
            model.fit(X_train, y_train)
            self.models['svm'] = model
            
            score = model.score(X_train, y_train)
            logger.info(f"SVM trained - Accuracy: {score:.4f}")
            
            return {
                'model': 'svm',
                'accuracy': score,
                'kernel': 'rbf'
            }
        except ImportError:
            logger.warning("SVM not available")
            return None
    
    def train_logistic_regression(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict:
        """Train Logistic Regression with regularization"""
        try:
            from sklearn.linear_model import LogisticRegression
            
            model = LogisticRegression(
                penalty='l2',
                C=1.0,
                solver='lbfgs',
                max_iter=1000,
                random_state=42,
                class_weight='balanced'
            )
            
            model.fit(X_train, y_train)
            self.models['logistic_regression'] = model
            
            score = model.score(X_train, y_train)
            logger.info(f"Logistic Regression trained - Accuracy: {score:.4f}")
            
            return {
                'model': 'logistic_regression',
                'accuracy': score,
                'coefficients': model.coef_
            }
        except ImportError:
            logger.warning("Logistic Regression not available")
            return None
    
    def ensemble_predict(self, X: np.ndarray, method: str = 'voting') -> np.ndarray:
        """Combine predictions from multiple models for robust results"""
        if not self.models:
            logger.warning("No trained models available")
            return None
        
        predictions = {}
        probabilities = {}
        
        for model_name, model in self.models.items():
            try:
                if hasattr(model, 'predict_proba'):
                    prob = model.predict_proba(X)[:, 1]
                    probabilities[model_name] = prob
                    predictions[model_name] = (prob > self.threshold_optimal).astype(int)
                else:
                    predictions[model_name] = model.predict(X)
            except Exception as e:
                logger.error(f"Error predicting with {model_name}: {e}")
        
        if method == 'voting':
            # Majority voting
            ensemble_pred = np.round(np.mean([predictions[m] for m in predictions], axis=0)).astype(int)
        elif method == 'weighted':
            # Weighted by model accuracy
            weights = {m: 1.0 for m in predictions}  # Can be adjusted
            ensemble_pred = np.round(np.average(
                [predictions[m] for m in predictions],
                axis=0,
                weights=list(weights.values())
            )).astype(int)
        else:
            # Average probability
            avg_prob = np.mean([probabilities[m] for m in probabilities if m in probabilities], axis=0)
            ensemble_pred = (avg_prob > self.threshold_optimal).astype(int)
        
        return ensemble_pred, probabilities


class AnomalyDetectionEvaluator:
    """Comprehensive evaluation of anomaly detection models"""
    
    @staticmethod
    def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray = None) -> Dict:
        """Calculate comprehensive evaluation metrics"""
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score, f1_score,
            roc_auc_score, confusion_matrix, matthews_corrcoef,
            cohen_kappa_score
        )
        
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1': f1_score(y_true, y_pred, zero_division=0),
            'mcc': matthews_corrcoef(y_true, y_pred),
            'kappa': cohen_kappa_score(y_true, y_pred)
        }
        
        if y_proba is not None:
            try:
                metrics['roc_auc'] = roc_auc_score(y_true, y_proba)
            except:
                metrics['roc_auc'] = None
        
        # Confusion matrix details
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        metrics['specificity'] = tn / (tn + fp) if (tn + fp) > 0 else 0
        metrics['sensitivity'] = tp / (tp + fn) if (tp + fn) > 0 else 0
        
        return metrics
    
    @staticmethod
    def get_feature_importance_analysis(model, feature_names: List[str]) -> pd.DataFrame:
        """Extract and rank feature importance from models"""
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
        elif hasattr(model, 'coef_'):
            importances = np.abs(model.coef_[0])
        else:
            return None
        
        importance_df = pd.DataFrame({
            'feature': feature_names,
            'importance': importances
        }).sort_values('importance', ascending=False)
        
        return importance_df


class RealTimeAnomalyDetector:
    """Real-time streaming anomaly detection"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.data_buffer = []
        self.predictions_buffer = []
        self.anomaly_score_buffer = []
        
    def update_stream(self, event: Dict, prediction: bool, anomaly_score: float):
        """Update with new streaming data"""
        self.data_buffer.append(event)
        self.predictions_buffer.append(prediction)
        self.anomaly_score_buffer.append(anomaly_score)
        
        # Keep only recent data
        if len(self.data_buffer) > self.window_size:
            self.data_buffer.pop(0)
            self.predictions_buffer.pop(0)
            self.anomaly_score_buffer.pop(0)
    
    def get_stream_statistics(self) -> Dict:
        """Calculate streaming statistics"""
        if not self.predictions_buffer:
            return {}
        
        return {
            'window_size': len(self.predictions_buffer),
            'anomaly_count': sum(self.predictions_buffer),
            'anomaly_rate': sum(self.predictions_buffer) / len(self.predictions_buffer),
            'avg_anomaly_score': np.mean(self.anomaly_score_buffer),
            'max_anomaly_score': np.max(self.anomaly_score_buffer),
            'trend': 'increasing' if np.mean(self.anomaly_score_buffer[-10:]) > np.mean(self.anomaly_score_buffer[:10]) else 'stable'
        }


class RegulationSpecificModels:
    """Specialized models for different regulations"""
    
    def __init__(self):
        self.gdpr_model = None
        self.ccpa_model = None
        self.pipl_model = None
        self.regulation_models = {}
    
    def train_gdpr_model(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict:
        """Train GDPR-specific compliance model"""
        from sklearn.ensemble import RandomForestClassifier
        
        model = RandomForestClassifier(
            n_estimators=150,
            max_depth=12,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_train, y_train)
        self.gdpr_model = model
        self.regulation_models['GDPR'] = model
        
        return {
            'regulation': 'GDPR',
            'accuracy': model.score(X_train, y_train),
            'estimators': 150
        }
    
    def train_ccpa_model(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict:
        """Train CCPA-specific compliance model"""
        from sklearn.ensemble import ExtraTreesClassifier
        
        model = ExtraTreesClassifier(
            n_estimators=150,
            max_depth=10,
            min_samples_split=8,
            min_samples_leaf=3,
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_train, y_train)
        self.ccpa_model = model
        self.regulation_models['CCPA'] = model
        
        return {
            'regulation': 'CCPA',
            'accuracy': model.score(X_train, y_train),
            'estimators': 150
        }
    
    def train_pipl_model(self, X_train: np.ndarray, y_train: np.ndarray) -> Dict:
        """Train PIPL-specific compliance model"""
        from sklearn.ensemble import GradientBoostingClassifier
        
        model = GradientBoostingClassifier(
            n_estimators=150,
            learning_rate=0.03,
            max_depth=6,
            random_state=42
        )
        
        model.fit(X_train, y_train)
        self.pipl_model = model
        self.regulation_models['PIPL'] = model
        
        return {
            'regulation': 'PIPL',
            'accuracy': model.score(X_train, y_train),
            'estimators': 150
        }
    
    def predict_with_regulation(self, X: np.ndarray, regulation: str) -> np.ndarray:
        """Predict using regulation-specific model"""
        if regulation in self.regulation_models:
            return self.regulation_models[regulation].predict(X)
        else:
            logger.warning(f"No model trained for regulation: {regulation}")
            return None


class ModelPerformanceTracker:
    """Track model performance metrics over time"""
    
    def __init__(self):
        self.performance_history = []
        self.evaluation_timestamps = []
    
    def record_evaluation(self, metrics: Dict, model_name: str = None, timestamp: datetime = None):
        """Record model evaluation results"""
        if timestamp is None:
            timestamp = datetime.now()
        
        record = {
            'timestamp': timestamp,
            'model': model_name,
            **metrics
        }
        
        self.performance_history.append(record)
        self.evaluation_timestamps.append(timestamp)
    
    def get_performance_trend(self, metric: str = 'accuracy') -> pd.DataFrame:
        """Get performance trend over time"""
        if not self.performance_history:
            return None
        
        df = pd.DataFrame(self.performance_history)
        return df[['timestamp', 'model', metric]].sort_values('timestamp')
    
    def get_best_model_by_metric(self, metric: str = 'f1') -> str:
        """Find best performing model"""
        if not self.performance_history:
            return None
        
        df = pd.DataFrame(self.performance_history)
        best_idx = df[metric].idxmax()
        return df.loc[best_idx, 'model']

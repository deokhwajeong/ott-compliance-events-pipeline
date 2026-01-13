"""Automated model retraining scheduler using APScheduler"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import pytz

logger = logging.getLogger(__name__)


class ModelRetrainingScheduler:
    """Manage automated model retraining and improvement"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False
        self.retraining_history: Dict[str, Any] = {}
        self.last_retraining_time: Dict[str, datetime] = {}
        self.retraining_metrics = {
            "anomaly_detector": {
                "total_retrainings": 0,
                "successful_retrainings": 0,
                "failed_retrainings": 0,
                "average_training_time_seconds": 0,
            },
            "adaptive_thresholds": {
                "total_retrainings": 0,
                "successful_retrainings": 0,
                "failed_retrainings": 0,
                "average_training_time_seconds": 0,
            },
            "network_fraud": {
                "total_updates": 0,
                "successful_updates": 0,
                "failed_updates": 0,
            },
        }
    
    def start(self) -> None:
        """Start the scheduler with all jobs"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        # Job 1: Retrain anomaly detection model daily at 2 AM UTC
        self.scheduler.add_job(
            self._retrain_anomaly_detector,
            trigger=CronTrigger(hour=2, minute=0, timezone=pytz.UTC),
            id="retrain_anomaly_detector",
            name="Retrain anomaly detector",
            replace_existing=True,
        )
        
        # Job 2: Update adaptive thresholds daily at 3 AM UTC
        self.scheduler.add_job(
            self._retrain_adaptive_thresholds,
            trigger=CronTrigger(hour=3, minute=0, timezone=pytz.UTC),
            id="retrain_adaptive_thresholds",
            name="Retrain adaptive thresholds",
            replace_existing=True,
        )
        
        # Job 3: Update network fraud rings every 6 hours
        self.scheduler.add_job(
            self._update_network_fraud_detection,
            trigger=IntervalTrigger(hours=6),
            id="update_network_fraud",
            name="Update network fraud detection",
            replace_existing=True,
        )
        
        # Job 4: Hourly cache cleanup
        self.scheduler.add_job(
            self._cleanup_old_cache,
            trigger=IntervalTrigger(hours=1),
            id="cleanup_cache",
            name="Cleanup old cache entries",
            replace_existing=True,
        )
        
        # Job 5: Daily model performance metrics report
        self.scheduler.add_job(
            self._generate_performance_report,
            trigger=CronTrigger(hour=4, minute=0, timezone=pytz.UTC),
            id="performance_report",
            name="Generate model performance report",
            replace_existing=True,
        )
        
        self.scheduler.start()
        self.is_running = True
        logger.info("Model retraining scheduler started with 5 jobs")
    
    def stop(self) -> None:
        """Stop the scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Model retraining scheduler stopped")
    
    def _retrain_anomaly_detector(self) -> None:
        """Retrain the ML anomaly detection model"""
        from ml_models import anomaly_detector
        import time
        
        logger.info("Starting anomaly detector retraining job...")
        start_time = time.time()
        
        try:
            # Check if we have enough data to retrain
            if len(anomaly_detector.feature_history) > 100:
                anomaly_detector.retrain_models()
                elapsed = time.time() - start_time
                
                # Update metrics
                self.retraining_metrics["anomaly_detector"]["total_retrainings"] += 1
                self.retraining_metrics["anomaly_detector"]["successful_retrainings"] += 1
                
                # Update average training time
                old_avg = self.retraining_metrics["anomaly_detector"]["average_training_time_seconds"]
                old_count = self.retraining_metrics["anomaly_detector"]["successful_retrainings"]
                new_avg = (old_avg * (old_count - 1) + elapsed) / old_count
                self.retraining_metrics["anomaly_detector"]["average_training_time_seconds"] = new_avg
                
                self.last_retraining_time["anomaly_detector"] = datetime.utcnow()
                logger.info(
                    f"Anomaly detector retraining completed in {elapsed:.2f}s. "
                    f"Samples: {len(anomaly_detector.feature_history)}"
                )
            else:
                logger.info(
                    f"Insufficient data for anomaly detector retraining. "
                    f"Samples: {len(anomaly_detector.feature_history)}/100"
                )
        except Exception as e:
            self.retraining_metrics["anomaly_detector"]["failed_retrainings"] += 1
            logger.error(f"Anomaly detector retraining failed: {e}")
    
    def _retrain_adaptive_thresholds(self) -> None:
        """Retrain the adaptive threshold model"""
        from adaptive_thresholds import adaptive_thresholds
        import time
        
        logger.info("Starting adaptive thresholds retraining job...")
        start_time = time.time()
        
        try:
            # Update thresholds based on recent violations
            adaptive_thresholds.update_thresholds_from_violations()
            elapsed = time.time() - start_time
            
            # Update metrics
            self.retraining_metrics["adaptive_thresholds"]["total_retrainings"] += 1
            self.retraining_metrics["adaptive_thresholds"]["successful_retrainings"] += 1
            
            old_avg = self.retraining_metrics["adaptive_thresholds"]["average_training_time_seconds"]
            old_count = self.retraining_metrics["adaptive_thresholds"]["successful_retrainings"]
            new_avg = (old_avg * (old_count - 1) + elapsed) / old_count
            self.retraining_metrics["adaptive_thresholds"]["average_training_time_seconds"] = new_avg
            
            self.last_retraining_time["adaptive_thresholds"] = datetime.utcnow()
            logger.info(f"Adaptive thresholds retraining completed in {elapsed:.2f}s")
        except Exception as e:
            self.retraining_metrics["adaptive_thresholds"]["failed_retrainings"] += 1
            logger.error(f"Adaptive thresholds retraining failed: {e}")
    
    def _update_network_fraud_detection(self) -> None:
        """Update network fraud detection rings"""
        from network_analysis import network_fraud_detector
        import time
        
        logger.info("Updating network fraud detection...")
        start_time = time.time()
        
        try:
            # Detect fraud rings
            rings = network_fraud_detector.detect_fraud_rings(min_ring_size=5)
            elapsed = time.time() - start_time
            
            self.retraining_metrics["network_fraud"]["total_updates"] += 1
            self.retraining_metrics["network_fraud"]["successful_updates"] += 1
            self.last_retraining_time["network_fraud"] = datetime.utcnow()
            
            logger.info(f"Network fraud detection updated in {elapsed:.2f}s. Found {len(rings)} fraud rings")
        except Exception as e:
            self.retraining_metrics["network_fraud"]["failed_updates"] += 1
            logger.error(f"Network fraud detection update failed: {e}")
    
    def _cleanup_old_cache(self) -> None:
        """Clean up old cache entries"""
        from cache import cache_manager
        
        try:
            # Clear pattern-based caches for old users
            cache_manager.clear_pattern("user:*:risk_profile")
            logger.debug("Cache cleanup completed")
        except Exception as e:
            logger.warning(f"Cache cleanup encountered error: {e}")
    
    def _generate_performance_report(self) -> None:
        """Generate daily model performance report"""
        logger.info("=" * 60)
        logger.info("DAILY MODEL PERFORMANCE REPORT")
        logger.info("=" * 60)
        
        for model_name, metrics in self.retraining_metrics.items():
            logger.info(f"\n{model_name.upper()}:")
            for metric_key, metric_value in metrics.items():
                if isinstance(metric_value, float):
                    logger.info(f"  {metric_key}: {metric_value:.2f}")
                else:
                    logger.info(f"  {metric_key}: {metric_value}")
        
        logger.info(f"\nLast Retraining Times:")
        for model_name, last_time in self.last_retraining_time.items():
            logger.info(f"  {model_name}: {last_time.isoformat()}")
        
        logger.info("=" * 60)
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status and metrics"""
        jobs = []
        if self.is_running:
            for job in self.scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                })
        
        return {
            "is_running": self.is_running,
            "scheduled_jobs": jobs,
            "metrics": self.retraining_metrics,
            "last_retraining_times": {
                k: v.isoformat() for k, v in self.last_retraining_time.items()
            },
        }
    
    def trigger_immediate_retraining(self, model_name: str) -> Dict[str, Any]:
        """Trigger immediate retraining for a specific model"""
        result = {"success": False, "message": ""}
        
        try:
            if model_name == "anomaly_detector":
                self._retrain_anomaly_detector()
                result["success"] = True
                result["message"] = "Anomaly detector retraining triggered"
            elif model_name == "adaptive_thresholds":
                self._retrain_adaptive_thresholds()
                result["success"] = True
                result["message"] = "Adaptive thresholds retraining triggered"
            elif model_name == "network_fraud":
                self._update_network_fraud_detection()
                result["success"] = True
                result["message"] = "Network fraud detection update triggered"
            else:
                result["message"] = f"Unknown model: {model_name}"
        except Exception as e:
            result["message"] = str(e)
        
        return result


# Global instance
model_scheduler = ModelRetrainingScheduler()

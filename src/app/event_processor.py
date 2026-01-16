import logging
import asyncio
from .queue import event_queue
from .kafka_config import kafka_settings
from .ml_models import anomaly_detector, violation_predictor
from .compliance_rules import evaluate_compliance
from .cache import cache_manager
from .alerting import alerting_system
from datetime import datetime
from typing import Dict, Any, List
import time

logger = logging.getLogger(__name__)

# Event processing statistics
_processing_stats = {
    "total_processed": 0,
    "anomalies_detected": 0,
    "violations_detected": 0,
    "avg_processing_time": 0.0,
    "errors": 0
}


async def process_events():
    """Background event processing with ML integration"""
    
    async def event_callback(event: dict):
        """Process individual event with comprehensive ML pipeline"""
        start_time = time.time()
        
        try:
            await process_single_event(event)
            _processing_stats["total_processed"] += 1
            
        except Exception as e:
            logger.error(f"Event processing error: {e}")
            _processing_stats["errors"] += 1
        
        # Update average processing time
        elapsed = time.time() - start_time
        n = _processing_stats["total_processed"]
        current_avg = _processing_stats["avg_processing_time"]
        _processing_stats["avg_processing_time"] = (
            (current_avg * (n - 1) + elapsed) / n if n > 0 else elapsed
        )
    
    if event_queue.use_kafka:
        await event_queue.subscribe_to_events(event_callback)
    else:
        logger.warning("Kafka not available - using local memory queue")


async def process_single_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprehensive event processing pipeline:
    1. Compliance evaluation
    2. ML anomaly detection
    3. Violation prediction
    4. Alerting
    5. Caching
    """
    
    user_id = event.get("user_id")
    event_type = event.get("event_type")
    
    logger.info(f"Processing event: {event_type} for user {user_id}")
    
    # Step 1: Evaluate compliance
    try:
        compliance_result = evaluate_compliance(event)
    except Exception as e:
        logger.error(f"Compliance evaluation failed: {e}")
        compliance_result = {"score": 0, "flags": [], "risk_level": "unknown"}
    
    # Step 2: ML Anomaly detection
    try:
        anomaly_result = anomaly_detector.ensemble_anomaly_detection(event)
        if anomaly_result["is_anomaly"]:
            _processing_stats["anomalies_detected"] += 1
            logger.warning(
                f"Anomaly detected for {user_id}: {anomaly_result['ensemble_score']:.2f}"
            )
    except Exception as e:
        logger.error(f"Anomaly detection failed: {e}")
        anomaly_result = {"is_anomaly": False, "ensemble_score": 0.0, "flags": []}
    
    # Step 3: Violation prediction (get recent events from cache or DB)
    try:
        # Get cached recent events
        cache_key = f"user:{user_id}:recent_events"
        recent_events = cache_manager.get(cache_key) or [event]
        
        violation_pred = violation_predictor.predict_violation_likelihood(
            recent_events,
            event
        )
        
        if violation_pred["violation_likelihood"] > 0.7:
            _processing_stats["violations_detected"] += 1
            logger.warning(
                f"High violation risk for {user_id}: "
                f"{violation_pred['violation_likelihood']:.2f}"
            )
    except Exception as e:
        logger.error(f"Violation prediction failed: {e}")
        violation_pred = {
            "violation_likelihood": 0.0,
            "risk_factors": [],
            "predicted_regulations": []
        }
    
    # Step 4: Alert if needed
    try:
        risk_level = compliance_result.get("risk_level", "low").lower()
        
        if risk_level == "high" or anomaly_result["is_anomaly"]:
            await alerting_system.send_alert(
                severity="HIGH",
                title=f"High Risk Event: {event_type}",
                message=f"User {user_id} triggered compliance violation",
                details={
                    "user_id": user_id,
                    "event_type": event_type,
                    "risk_score": compliance_result.get("score", 0),
                    "anomaly_score": anomaly_result.get("ensemble_score", 0),
                    "compliance_flags": compliance_result.get("flags", []),
                    "violation_likelihood": violation_pred.get("violation_likelihood", 0)
                }
            )
    except Exception as e:
        logger.error(f"Alerting failed: {e}")
    
    # Step 5: Update cache
    try:
        cache_key = f"user:{user_id}:recent_events"
        cached_events = cache_manager.get(cache_key) or []
        cached_events.append(event)
        cached_events = cached_events[-50:]  # Keep last 50 events
        
        cache_manager.set(cache_key, cached_events, ttl=3600)  # 1 hour TTL
        
        # Cache risk profile
        risk_profile_key = f"user:{user_id}:risk_profile"
        risk_profile = {
            "last_updated": datetime.utcnow().isoformat(),
            "compliance_score": compliance_result.get("score", 0),
            "anomaly_score": anomaly_result.get("ensemble_score", 0),
            "violation_likelihood": violation_pred.get("violation_likelihood", 0),
            "risk_level": risk_level
        }
        cache_manager.set(risk_profile_key, risk_profile, ttl=600)  # 10 min TTL
        
    except Exception as e:
        logger.error(f"Cache update failed: {e}")
    
    return {
        "event_id": event.get("event_id"),
        "user_id": user_id,
        "compliance": compliance_result,
        "anomaly": anomaly_result,
        "violation": violation_pred,
        "processed_at": datetime.utcnow().isoformat()
    }


def get_processing_stats() -> Dict[str, Any]:
    """Get event processing statistics"""
    return _processing_stats.copy()


def reset_processing_stats():
    """Reset processing statistics"""
    global _processing_stats
    _processing_stats = {
        "total_processed": 0,
        "anomalies_detected": 0,
        "violations_detected": 0,
        "avg_processing_time": 0.0,
        "errors": 0
    }

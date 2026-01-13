from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import RawEvent, ProcessedEvent
import numpy as np
from sklearn.preprocessing import StandardScaler
import logging

# Import new ML modules
from .geoip_validator import geoip_validator
from .ml_models import anomaly_detector, violation_predictor
from .adaptive_thresholds import adaptive_thresholds
from .cache import cache_manager
from .user_segments import user_segmentation
from .network_analysis import network_fraud_detector
from .regulations import compliance_checker
from .alerting import alerting_system
import asyncio

logger = logging.getLogger(__name__)


def detect_anomaly_with_ml(scores: list) -> bool:
    """
    Simple ML-based anomaly detection using z-score.
    Returns True if the last score is anomalous.
    """
    if len(scores) < 3:
        return False
    
    scaler = StandardScaler()
    scores_array = np.array(scores).reshape(-1, 1)
    scaled_scores = scaler.fit_transform(scores_array)
    
    # Z-score of the last score
    z_score = scaled_scores[-1][0]
    return abs(z_score) > 2.0  # Threshold for anomaly


def evaluate_compliance(event: Dict[str, Any], db: Session = None) -> Dict[str, Any]:
    """
    Enhanced compliance evaluation with ML, GeoIP validation, and multi-country rules.
    Integrates all new compliance modules into a comprehensive risk assessment.
    """
    flags = []
    score = 0.0
    detailed_findings = {}

    event_type = (event.get("event_type") or "").lower()
    region = event.get("region", "unknown")
    user_id = event.get("user_id")
    device_id = event.get("device_id")
    ip_address = event.get("ip_address")
    timestamp = event.get("timestamp")
    is_eu = event.get("is_eu", False)
    has_consent = event.get("has_consent", True)
    subscription_plan = event.get("subscription_plan", "basic")
    content_id = event.get("content_id")
    payment_method = event.get("payment_method")

    # ========================
    # 1. GeoIP Validation
    # ========================
    if ip_address and region:
        try:
            geoip_result = geoip_validator.validate_ip_region_consistency(ip_address, region)
            if not geoip_result.get("region_match", True):
                flags.append("geoip_region_mismatch")
                score += geoip_result.get("risk_score", 0.5)
                detailed_findings["geoip_validation"] = geoip_result
            
            # Check for impossible travel
            if user_id:
                travel_result = geoip_validator.detect_impossible_travel(user_id, ip_address)
                if travel_result.get("impossible_travel", False):
                    flags.append("impossible_travel_detected")
                    score += 3.0
                    detailed_findings["impossible_travel"] = travel_result
        except Exception as e:
            logger.warning(f"GeoIP validation failed: {e}")

    # ========================
    # 2. Missing Identifiers
    # ========================
    if not user_id:
        flags.append("missing_user_id")
        score += 2
    if not device_id:
        flags.append("missing_device_id")
        score += 2

    # ========================
    # 3. Basic Event Type Rules
    # ========================
    if event_type in {"error", "login_failed", "token_refresh_failed"}:
        flags.append("auth_or_playback_error")
        score += 3

    # ========================
    # 4. Consent and Privacy
    # ========================
    if is_eu and not has_consent:
        flags.append("eu_privacy_violation")
        score += 5

    # ========================
    # 5. User Segmentation
    # ========================
    user_segment = None
    user_risk_params = None
    if db and user_id:
        try:
            # Get user metrics
            all_events = db.query(RawEvent).filter(RawEvent.user_id == user_id).all()
            
            if all_events:
                now = datetime.utcnow()
                thirty_days_ago = now - timedelta(days=30)
                seven_days_ago = now - timedelta(days=7)
                
                events_30d = [e for e in all_events if e.timestamp >= thirty_days_ago]
                events_7d = [e for e in all_events if e.timestamp >= seven_days_ago]
                
                violations_30d = db.query(ProcessedEvent).filter(
                    ProcessedEvent.event_id.in_([e.event_id for e in events_30d]),
                    ProcessedEvent.risk_level.in_(["high", "critical"])
                ).count()
                
                days_since_signup = max(1, (now - min(e.timestamp for e in all_events)).days)
                last_activity_days = (now - max(e.timestamp for e in all_events)).days
                avg_risk = sum(
                    db.query(ProcessedEvent.risk_score).filter(
                        ProcessedEvent.event_id == e.event_id
                    ).scalar() or 0.0 for e in events_30d
                ) / len(events_30d) if events_30d else 0.0
                
                user_segment = user_segmentation.update_user_profile(
                    user_id=user_id,
                    event_count_30d=len(events_30d),
                    event_count_7d=len(events_7d),
                    violation_count_30d=violations_30d,
                    days_since_signup=days_since_signup,
                    last_activity_days_ago=last_activity_days,
                    avg_risk_score=avg_risk
                )
                
                user_risk_params = user_segmentation.get_segment_risk_parameters(user_segment)
                detailed_findings["user_segment"] = {
                    "segment": user_segment.value,
                    "risk_parameters": user_risk_params,
                }
        except Exception as e:
            logger.warning(f"User segmentation failed: {e}")

    # ========================
    # 6. Adaptive Threshold Adjustment
    # ========================
    try:
        dynamic_threshold = adaptive_thresholds.get_dynamic_risk_threshold(
            region=region,
            user_segment=user_segment,
            time_of_day_utc=datetime.utcnow().hour
        )
        detailed_findings["adaptive_threshold"] = dynamic_threshold
    except Exception as e:
        logger.warning(f"Adaptive threshold calculation failed: {e}")
        dynamic_threshold = 8.0

    # ========================
    # 7. Network Fraud Detection
    # ========================
    if user_id:
        try:
            network_fraud_detector.add_user_event(
                user_id=user_id,
                device_id=device_id,
                ip_address=ip_address,
                payment_method=payment_method
            )
            
            network_risk = network_fraud_detector.get_user_network_risk(user_id, max_hops=2)
            
            if network_risk.get("risk_score", 0) > 0.5:
                flags.append("fraud_ring_connection")
                score += network_risk["risk_score"] * 2.0
            
            detailed_findings["network_analysis"] = network_risk
        except Exception as e:
            logger.warning(f"Network fraud detection failed: {e}")

    # ========================
    # 8. Enhanced ML Anomaly Detection
    # ========================
    ml_result = None
    if db and user_id:
        try:
            # Extract features from event
            event_features = {
                "hour": datetime.utcnow().hour,
                "weekday": datetime.utcnow().weekday(),
                "event_type_len": len(event_type),
                "has_error": int(event_type in {"error", "login_failed"}),
                "is_eu": int(is_eu),
                "has_consent": int(has_consent),
                "subscription_tier": {"basic": 1, "standard": 2, "premium": 3}.get(subscription_plan, 1),
                "device_id": hash(device_id) % 1000 if device_id else 0,
                "region_code": hash(region) % 100 if region else 0,
            }
            
            # Use ensemble anomaly detection
            ml_result = anomaly_detector.ensemble_anomaly_detection(event_features)
            
            if ml_result["is_anomaly"]:
                flags.append("ml_ensemble_anomaly")
                score += ml_result.get("anomaly_score", 2.0)
            
            # Add to feature history for continuous learning
            anomaly_detector._add_to_history(event_features, is_violation=False)
            
            detailed_findings["ml_anomaly_detection"] = ml_result
        except Exception as e:
            logger.warning(f"ML anomaly detection failed: {e}")

    # ========================
    # 9. Violation Prediction
    # ========================
    if user_id:
        try:
            violation_pred = violation_predictor.predict_violation_likelihood(
                user_id=user_id,
                recent_events_count=db.query(RawEvent).filter(
                    RawEvent.user_id == user_id
                ).count() if db else 0,
                average_risk_score=score
            )
            
            if violation_pred.get("violation_likelihood", 0) > 0.7:
                flags.append("high_violation_risk")
                score += violation_pred.get("violation_likelihood", 0.7) * 2.0
            
            detailed_findings["violation_prediction"] = violation_pred
        except Exception as e:
            logger.warning(f"Violation prediction failed: {e}")

    # ========================
    # 10. Multi-Country Compliance Check
    # ========================
    try:
        compliance_result = compliance_checker.evaluate_event_compliance(
            user_id=user_id or "unknown",
            event_type=event_type,
            region=region,
            event_details={"has_explicit_consent": has_consent}
        )
        
        if not compliance_result["compliant"]:
            flags.append("multi_country_violation")
            score += len(compliance_result["violations"]) * 2.0
        
        detailed_findings["compliance_check"] = compliance_result
    except Exception as e:
        logger.warning(f"Compliance check failed: {e}")

    # ========================
    # 11. Subscription-Based Adjustment
    # ========================
    if subscription_plan == "premium":
        score = max(0, score - 1)
    elif subscription_plan == "basic":
        score += 1

    # ========================
    # 12. Time-Window Analysis
    # ========================
    if db and user_id and timestamp:
        try:
            event_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            window_start = event_time - timedelta(hours=1)
            
            recent_events = db.query(RawEvent).filter(
                RawEvent.user_id == user_id,
                RawEvent.timestamp >= window_start,
                RawEvent.timestamp <= event_time
            ).all()
            
            regions_in_window = set(e.region for e in recent_events)
            if len(regions_in_window) > 2:
                flags.append("multi_region_access")
                score += 2
            
            if len(recent_events) > 10:
                flags.append("high_frequency_activity")
                score += 1
        except Exception as e:
            logger.warning(f"Time-window analysis failed: {e}")

    # ========================
    # 13. Determine Risk Level
    # ========================
    # Use adaptive threshold if available
    threshold_high = dynamic_threshold if dynamic_threshold else 8.0
    threshold_medium = max(0, threshold_high - 3.0)
    
    if score >= threshold_high:
        risk_level = "high"
    elif score >= threshold_medium:
        risk_level = "medium"
    else:
        risk_level = "low"

    result = {
        "score": round(score, 2),
        "risk_level": risk_level,
        "flags": flags,
        "detailed_findings": detailed_findings,
    }

    # ========================
    # 14. Record Metrics and Trigger Alerts
    # ========================
    if db and risk_level in ["high", "critical"]:
        try:
            # Record for adaptive threshold learning
            adaptive_thresholds.record_event(
                region=region,
                time_of_day=datetime.utcnow().hour,
                score=score,
                violation=risk_level == "high"
            )
            
            # Update ML history with violation
            if ml_result:
                anomaly_detector._add_to_history(
                    ml_result.get("features", {}),
                    is_violation=True
                )
            
            # Send alert for high-risk events
            try:
                asyncio.create_task(
                    alerting_system.send_alert(
                        severity="HIGH" if risk_level == "high" else "CRITICAL",
                        title=f"High-risk event detected for user {user_id}",
                        message=f"Risk score: {score}. Flags: {', '.join(flags)}",
                        details=result
                    )
                )
            except Exception as e:
                logger.warning(f"Could not send alert: {e}")
        except Exception as e:
            logger.warning(f"Failed to record metrics: {e}")

    return result

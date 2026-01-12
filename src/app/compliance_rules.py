from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import RawEvent, ProcessedEvent
import numpy as np
from sklearn.preprocessing import StandardScaler

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
    Return risk flags + score.
    Enhanced rules: time-window based detection, subscription impact, etc.
    """
    flags = []
    score = 0

    event_type = (event.get("event_type") or "").lower()
    region = event.get("region")
    user_id = event.get("user_id")
    device_id = event.get("device_id")
    timestamp = event.get("timestamp")
    is_eu = event.get("is_eu", False)
    has_consent = event.get("has_consent", True)
    subscription_plan = event.get("subscription_plan", "basic")

    # Missing identifiers (privacy/account risk)
    if not user_id:
        flags.append("missing_user_id")
        score += 2
    if not device_id:
        flags.append("missing_device_id")
        score += 2

    # Suspicious actions
    if event_type in {"error", "login_failed", "token_refresh_failed"}:
        flags.append("auth_or_playback_error")
        score += 3

    # EU privacy risk
    if is_eu and not has_consent:
        flags.append("eu_privacy_violation")
        score += 5

    # Subscription-based risk adjustment
    if subscription_plan == "premium":
        score = max(0, score - 1)  # Premium users get slight benefit
    elif subscription_plan == "basic":
        score += 1  # Basic users slightly higher risk

    # Time-window based detection (requires DB)
    if db and user_id and timestamp:
        try:
            event_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            window_start = event_time - timedelta(hours=1)
            
            # Check recent events from same user
            recent_events = db.query(RawEvent).filter(
                RawEvent.user_id == user_id,
                RawEvent.timestamp >= window_start,
                RawEvent.timestamp <= event_time
            ).all()
            
            regions_in_window = set(e.region for e in recent_events)
            if len(regions_in_window) > 2:
                flags.append("multi_region_access")
                score += 4
            
            # High frequency events
            if len(recent_events) > 10:
                flags.append("high_frequency_activity")
                score += 2
                
        except Exception as e:
            # If DB query fails, skip time-window rules
            pass

    # ML-based anomaly detection
    if db and user_id:
        try:
            # Get recent processed events for this user
            recent_processed = db.query(ProcessedEvent).filter(
                ProcessedEvent.user_id == user_id
            ).order_by(ProcessedEvent.processed_at.desc()).limit(10).all()
            
            if recent_processed:
                recent_scores = [p.risk_score for p in recent_processed]
                if detect_anomaly_with_ml(recent_scores):
                    flags.append("ml_anomaly_detected")
                    score += 3
        except Exception as e:
            # If DB query fails, skip ML detection
            pass

    risk_level = "low"
    if score >= 8:
        risk_level = "high"
    elif score >= 4:
        risk_level = "medium"

    return {"score": score, "risk_level": risk_level, "flags": flags}

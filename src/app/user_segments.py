"""User segmentation for differentiated compliance rules"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
import joblib
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)


class UserSegment(str, Enum):
    """User segment classifications"""
    POWER_USER = "power_user"
    NORMAL_USER = "normal_user"
    NEW_USER = "new_user"
    INACTIVE_USER = "inactive_user"
    SUSPICIOUS_USER = "suspicious_user"
    DORMANT_USER = "dormant_user"


class UserSegmentationEngine:
    """Segment users for differentiated risk analysis"""
    
    def __init__(self):
        self.user_profiles: Dict[str, Dict] = {}
        self.model_path = MODEL_DIR / "user_segmentation.pkl"
        self.load_model()
    
    def classify_user(
        self,
        user_id: str,
        event_count_30d: int,
        event_count_7d: int,
        violation_count_30d: int,
        days_since_signup: int,
        last_activity_days_ago: int,
        avg_risk_score: float
    ) -> UserSegment:
        """
        Classify user into segment based on behavior metrics.
        """
        # Power users: lots of activity, low violations, long-term
        if event_count_30d > 500 and violation_count_30d == 0 and days_since_signup > 180:
            return UserSegment.POWER_USER
        
        # New users: recent signup, low activity
        if days_since_signup < 30 and event_count_30d < 50:
            return UserSegment.NEW_USER
        
        # Suspicious: high violation rate or sudden spike in activity
        if violation_count_30d > 5 or (event_count_7d > event_count_30d / 4 * 7):
            return UserSegment.SUSPICIOUS_USER
        
        # Inactive: no recent activity
        if last_activity_days_ago > 90 and event_count_30d == 0:
            return UserSegment.DORMANT_USER
        
        # Returning inactive: low recent activity but was active before
        if last_activity_days_ago > 30 and 10 < event_count_30d < 100:
            return UserSegment.INACTIVE_USER
        
        # Normal: regular activity, low violations
        return UserSegment.NORMAL_USER
    
    def get_segment_risk_parameters(self, segment: UserSegment) -> Dict[str, Any]:
        """
        Get risk parameters specific to user segment.
        Different segments have different baseline thresholds.
        """
        parameters = {
            UserSegment.POWER_USER: {
                "risk_threshold_high": 9.0,  # More lenient
                "risk_threshold_medium": 6.0,
                "anomaly_sensitivity": 0.8,  # Less sensitive
                "alert_channels": ["log"],  # Only log, don't spam
                "alert_severity_multiplier": 0.8,
            },
            UserSegment.NORMAL_USER: {
                "risk_threshold_high": 8.0,  # Default
                "risk_threshold_medium": 5.0,
                "anomaly_sensitivity": 1.0,  # Normal
                "alert_channels": ["log", "slack"],
                "alert_severity_multiplier": 1.0,
            },
            UserSegment.NEW_USER: {
                "risk_threshold_high": 7.0,  # Stricter
                "risk_threshold_medium": 4.0,
                "anomaly_sensitivity": 1.3,  # More sensitive
                "alert_channels": ["log", "slack", "email"],
                "alert_severity_multiplier": 1.2,
            },
            UserSegment.INACTIVE_USER: {
                "risk_threshold_high": 7.0,  # Stricter (suspicious to return)
                "risk_threshold_medium": 4.0,
                "anomaly_sensitivity": 1.2,
                "alert_channels": ["log", "slack"],
                "alert_severity_multiplier": 1.1,
            },
            UserSegment.SUSPICIOUS_USER: {
                "risk_threshold_high": 6.0,  # Very strict
                "risk_threshold_medium": 3.0,
                "anomaly_sensitivity": 1.5,  # Very sensitive
                "alert_channels": ["log", "slack", "email", "sms"],
                "alert_severity_multiplier": 1.5,
            },
            UserSegment.DORMANT_USER: {
                "risk_threshold_high": 7.0,
                "risk_threshold_medium": 4.0,
                "anomaly_sensitivity": 1.1,
                "alert_channels": ["log", "slack"],
                "alert_severity_multiplier": 1.2,
            },
        }
        
        return parameters.get(segment, parameters[UserSegment.NORMAL_USER])
    
    def update_user_profile(
        self,
        user_id: str,
        event_count_30d: int,
        event_count_7d: int,
        violation_count_30d: int,
        days_since_signup: int,
        last_activity_days_ago: int,
        avg_risk_score: float
    ) -> UserSegment:
        """Update user profile and return new segment"""
        segment = self.classify_user(
            user_id,
            event_count_30d,
            event_count_7d,
            violation_count_30d,
            days_since_signup,
            last_activity_days_ago,
            avg_risk_score
        )
        
        self.user_profiles[user_id] = {
            "segment": segment.value,
            "event_count_30d": event_count_30d,
            "event_count_7d": event_count_7d,
            "violation_count_30d": violation_count_30d,
            "days_since_signup": days_since_signup,
            "last_activity_days_ago": last_activity_days_ago,
            "avg_risk_score": avg_risk_score,
            "last_updated": datetime.utcnow().isoformat(),
        }
        
        return segment
    
    def get_user_segment(self, user_id: str) -> UserSegment:
        """Get current segment for user"""
        if user_id in self.user_profiles:
            segment_str = self.user_profiles[user_id]["segment"]
            return UserSegment(segment_str)
        
        # Default to normal if not profiled yet
        return UserSegment.NORMAL_USER
    
    def get_segment_statistics(self) -> Dict[str, Any]:
        """Get statistics about user segments"""
        segment_counts = {}
        
        for profile in self.user_profiles.values():
            segment = profile["segment"]
            segment_counts[segment] = segment_counts.get(segment, 0) + 1
        
        return {
            "total_users": len(self.user_profiles),
            "segment_distribution": segment_counts,
        }
    
    def save_model(self) -> None:
        """Save user profiles to disk"""
        try:
            joblib.dump(self.user_profiles, self.model_path)
            logger.info("User segmentation model saved")
        except Exception as e:
            logger.error(f"Failed to save user segmentation: {e}")
    
    def load_model(self) -> None:
        """Load user profiles from disk"""
        try:
            if self.model_path.exists():
                self.user_profiles = joblib.load(self.model_path)
                logger.info(f"Loaded {len(self.user_profiles)} user profiles")
        except Exception as e:
            logger.warning(f"Could not load user segmentation: {e}")


# Global instance
user_segmentation = UserSegmentationEngine()

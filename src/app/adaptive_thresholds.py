"""Adaptive thresholds that learn from data patterns"""

import logging
from typing import Dict, Any
from datetime import datetime
from collections import defaultdict
import numpy as np
import joblib
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)


class AdaptiveThresholds:
    """Learn and adapt risk thresholds based on temporal and regional patterns"""
    
    def __init__(self):
        self.time_of_day_stats = defaultdict(lambda: {"scores": [], "violations": []})
        self.region_stats = defaultdict(lambda: {"scores": [], "violations": []})
        self.user_segment_stats = defaultdict(lambda: {"scores": [], "violations": []})
        self.model_path = MODEL_DIR / "adaptive_thresholds.pkl"
        self.load_model()
    
    def get_dynamic_risk_threshold(
        self,
        user_segment: str,
        hour: int,
        region: str
    ) -> float:
        """
        Get adaptive risk threshold based on:
        - Time of day (different patterns for morning vs night)
        - Region (different baselines per country)
        - User segment (power users vs casual users)
        """
        base_threshold = 8.0  # Default threshold for HIGH risk
        
        # Time-of-day adjustment
        time_adjustment = self._get_time_adjustment(hour)
        
        # Region adjustment
        region_adjustment = self._get_region_adjustment(region)
        
        # User segment adjustment
        segment_adjustment = self._get_segment_adjustment(user_segment)
        
        # Combine adjustments (multiplicative)
        final_threshold = base_threshold * (1.0 + time_adjustment + region_adjustment + segment_adjustment)
        
        # Clamp to reasonable range
        return max(4.0, min(12.0, final_threshold))
    
    def record_event(
        self,
        risk_score: float,
        is_violation: bool,
        user_segment: str,
        hour: int,
        region: str
    ) -> None:
        """Record event data for threshold learning"""
        # Store time-of-day statistics
        self.time_of_day_stats[hour]["scores"].append(risk_score)
        if is_violation:
            self.time_of_day_stats[hour]["violations"].append(risk_score)
        
        # Store region statistics
        self.region_stats[region]["scores"].append(risk_score)
        if is_violation:
            self.region_stats[region]["violations"].append(risk_score)
        
        # Store user segment statistics
        self.user_segment_stats[user_segment]["scores"].append(risk_score)
        if is_violation:
            self.user_segment_stats[user_segment]["violations"].append(risk_score)
    
    def _get_time_adjustment(self, hour: int) -> float:
        """
        Adjust threshold based on time of day.
        Night activity (2-5 AM) is more suspicious than day activity (9-17).
        """
        hour_adjustments = {
            0: 0.15, 1: 0.20, 2: 0.25, 3: 0.30, 4: 0.25, 5: 0.20,  # Night: higher risk
            6: 0.10, 7: 0.05, 8: 0.00, 9: -0.10, 10: -0.15, 11: -0.15,  # Morning: normal
            12: -0.15, 13: -0.10, 14: -0.10, 15: -0.10, 16: -0.05, 17: 0.00,  # Day: lowest risk
            18: 0.05, 19: 0.10, 20: 0.10, 21: 0.10, 22: 0.10, 23: 0.15  # Evening: higher
        }
        
        return hour_adjustments.get(hour, 0.0)
    
    def _get_region_adjustment(self, region: str) -> float:
        """
        Adjust threshold based on region.
        Some regions have more fraud/violations naturally.
        """
        # Learn from violations if available
        stats = self.region_stats.get(region, {})
        
        if not stats.get("violations"):
            return 0.0
        
        violation_rate = len(stats["violations"]) / max(len(stats["scores"]), 1)
        
        # If violation rate is high, lower threshold to catch more
        if violation_rate > 0.2:  # 20% violation rate
            return -0.2  # Make threshold tighter
        elif violation_rate > 0.1:
            return -0.1
        
        return 0.0
    
    def _get_segment_adjustment(self, user_segment: str) -> float:
        """
        Adjust threshold based on user segment.
        Power users might have higher scores but still legitimate.
        """
        segment_adjustments = {
            "power_user": -0.2,  # More lenient (higher threshold)
            "normal_user": 0.0,  # Default
            "new_user": 0.2,  # Stricter (lower threshold)
            "inactive_user": 0.15,  # Stricter for returning users
            "suspicious": 0.3,  # Very strict
        }
        
        return segment_adjustments.get(user_segment, 0.0)
    
    def update_thresholds_from_violations(self) -> None:
        """Update thresholds based on collected violation data"""
        try:
            # Update region thresholds based on violation patterns
            for region, stats in self.region_stats.items():
                if len(stats["violations"]) >= 5:
                    # Calculate percentile where violations typically occur
                    violation_threshold = np.percentile(stats["violations"], 25)
                    logger.info(f"Region {region} violation threshold: {violation_threshold:.1f}")
            
            self.save_model()
        except Exception as e:
            logger.error(f"Error updating thresholds: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current threshold statistics"""
        return {
            "time_of_day_stats": dict(self.time_of_day_stats),
            "region_stats": dict(self.region_stats),
            "user_segment_stats": dict(self.user_segment_stats),
        }
    
    def save_model(self) -> None:
        """Save adaptive thresholds to disk"""
        try:
            data = {
                "time_of_day_stats": dict(self.time_of_day_stats),
                "region_stats": dict(self.region_stats),
                "user_segment_stats": dict(self.user_segment_stats),
            }
            joblib.dump(data, self.model_path)
            logger.info("Adaptive thresholds saved")
        except Exception as e:
            logger.error(f"Failed to save thresholds: {e}")
    
    def load_model(self) -> None:
        """Load adaptive thresholds from disk"""
        try:
            if self.model_path.exists():
                data = joblib.load(self.model_path)
                self.time_of_day_stats = defaultdict(
                    lambda: {"scores": [], "violations": []},
                    data.get("time_of_day_stats", {})
                )
                self.region_stats = defaultdict(
                    lambda: {"scores": [], "violations": []},
                    data.get("region_stats", {})
                )
                self.user_segment_stats = defaultdict(
                    lambda: {"scores": [], "violations": []},
                    data.get("user_segment_stats", {})
                )
                logger.info("Adaptive thresholds loaded")
        except Exception as e:
            logger.warning(f"Could not load thresholds: {e}")


# Global instance
adaptive_thresholds = AdaptiveThresholds()

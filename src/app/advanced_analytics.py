"""Advanced reporting and analytics module"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from sqlalchemy.orm import Session
import json

logger = logging.getLogger(__name__)


class AdvancedAnalytics:
    """Advanced analytics and reporting"""
    
    @staticmethod
    def get_risk_distribution(processed_events: List[Any]) -> Dict[str, int]:
        """Get distribution of risk levels"""
        distribution = {"low": 0, "medium": 0, "high": 0}
        
        for event in processed_events:
            risk_level = getattr(event, 'risk_level', 'low').lower()
            if risk_level in distribution:
                distribution[risk_level] += 1
        
        return distribution
    
    @staticmethod
    def get_violation_trends(processed_events: List[Any], days: int = 7) -> Dict[str, Any]:
        """Get violation trends over time"""
        trends = {}
        
        for event in processed_events:
            if hasattr(event, 'processed_at'):
                day = event.processed_at.date().isoformat()
                if day not in trends:
                    trends[day] = {
                        "total": 0,
                        "violations": 0,
                        "risk_score_avg": 0.0
                    }
                
                trends[day]["total"] += 1
                risk_score = getattr(event, 'risk_score', 0)
                trends[day]["risk_score_avg"] = (
                    (trends[day]["risk_score_avg"] * (trends[day]["total"] - 1) + risk_score) /
                    trends[day]["total"]
                )
        
        return trends
    
    @staticmethod
    def get_top_risk_factors(events: List[Dict]) -> List[Dict[str, Any]]:
        """Get most common risk factors"""
        factor_counts = {}
        
        for event in events:
            flags = event.get("flags", []) if isinstance(event.get("flags"), list) else []
            for flag in flags:
                factor_counts[flag] = factor_counts.get(flag, 0) + 1
        
        # Sort by frequency
        sorted_factors = sorted(
            factor_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {"factor": factor, "count": count}
            for factor, count in sorted_factors[:10]
        ]
    
    @staticmethod
    def get_user_segmentation_stats(user_segments: Dict[str, List[str]]) -> Dict[str, int]:
        """Get count of users in each segment"""
        return {
            segment: len(users)
            for segment, users in user_segments.items()
        }
    
    @staticmethod
    def get_geographic_distribution(events: List[Dict]) -> Dict[str, int]:
        """Get distribution of events by region"""
        regions = {}
        
        for event in events:
            region = event.get("region", "unknown")
            regions[region] = regions.get(region, 0) + 1
        
        return dict(sorted(regions.items(), key=lambda x: x[1], reverse=True))
    
    @staticmethod
    def get_compliance_summary(db: Session) -> Dict[str, Any]:
        """Get overall compliance summary"""
        try:
            from .models import ProcessedEvent
            
            all_events = db.query(ProcessedEvent).all()
            
            if not all_events:
                return {
                    "total_events": 0,
                    "compliance_score": 0.0,
                    "risk_distribution": {"low": 0, "medium": 0, "high": 0}
                }
            
            risk_dist = AdvancedAnalytics.get_risk_distribution(all_events)
            total = sum(risk_dist.values())
            
            # Calculate compliance score (inverse of violations)
            violations = risk_dist.get("high", 0) + risk_dist.get("medium", 0)
            compliance_score = ((total - violations) / total * 100) if total > 0 else 0
            
            return {
                "total_events": total,
                "compliance_score": round(compliance_score, 2),
                "risk_distribution": risk_dist,
                "violation_rate": round((violations / total * 100), 2) if total > 0 else 0
            }
        except Exception as e:
            logger.error(f"Error getting compliance summary: {e}")
            return {"error": str(e)}


class ReportGenerator:
    """Generate various reports"""
    
    @staticmethod
    def generate_executive_summary(db: Session) -> Dict[str, Any]:
        """Generate executive summary report"""
        try:
            from .models import RawEvent, ProcessedEvent
            
            total_raw_events = db.query(RawEvent).count()
            total_processed = db.query(ProcessedEvent).count()
            
            compliance_summary = AdvancedAnalytics.get_compliance_summary(db)
            
            return {
                "report_type": "executive_summary",
                "generated_at": datetime.utcnow().isoformat(),
                "total_events_received": total_raw_events,
                "total_events_processed": total_processed,
                "compliance": compliance_summary,
                "processing_rate": round(total_processed / max(total_raw_events, 1) * 100, 2)
            }
        except Exception as e:
            logger.error(f"Error generating executive summary: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def generate_compliance_report(db: Session, days: int = 7) -> Dict[str, Any]:
        """Generate detailed compliance report"""
        try:
            from .models import ProcessedEvent, RawEvent
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            recent_events = db.query(ProcessedEvent).filter(
                ProcessedEvent.processed_at >= cutoff_date
            ).all()
            
            recent_raw = db.query(RawEvent).filter(
                RawEvent.timestamp >= cutoff_date
            ).all()
            
            # Convert to dicts for analysis
            events_dict = [
                {
                    "risk_score": e.risk_score,
                    "risk_level": e.risk_level,
                    "flags": json.loads(e.flags) if isinstance(e.flags, str) else e.flags
                }
                for e in recent_events
            ]
            
            trends = AdvancedAnalytics.get_violation_trends(recent_events, days)
            risk_factors = AdvancedAnalytics.get_top_risk_factors(events_dict)
            
            return {
                "report_type": "compliance_report",
                "period_days": days,
                "generated_at": datetime.utcnow().isoformat(),
                "summary": AdvancedAnalytics.get_compliance_summary(db),
                "trends": trends,
                "top_risk_factors": risk_factors,
                "event_count": len(recent_events)
            }
        except Exception as e:
            logger.error(f"Error generating compliance report: {e}")
            return {"error": str(e)}
    
    @staticmethod
    def generate_ml_performance_report(ml_metrics: Dict) -> Dict[str, Any]:
        """Generate ML model performance report"""
        return {
            "report_type": "ml_performance",
            "generated_at": datetime.utcnow().isoformat(),
            "metrics": ml_metrics,
            "timestamp": datetime.utcnow().isoformat()
        }


# Global analytics instance
advanced_analytics = AdvancedAnalytics()
report_generator_advanced = ReportGenerator()


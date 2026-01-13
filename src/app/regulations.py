"""Multi-country compliance regulations support"""

import logging
from typing import Dict, List, Any
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class Regulation(str, Enum):
    """Supported compliance regulations"""
    GDPR = "GDPR"  # EU - General Data Protection Regulation
    CCPA = "CCPA"  # California - California Consumer Privacy Act
    PIPL = "PIPL"  # China - Personal Information Protection Law
    PDPA = "PDPA"  # Thailand - Personal Data Protection Act
    LGPD = "LGPD"  # Brazil - Lei Geral de Proteção de Dados
    POPIA = "POPIA"  # South Africa - Protection of Personal Information Act
    APRA = "APRA"  # Australia - Privacy Act
    PIPEDA = "PIPEDA"  # Canada - Personal Information Protection and Electronic Documents Act
    KVKK = "KVKK"  # Turkey - Kişisel Verileri Koruma Kanunu
    PDPL = "PDPL"  # Singapore - Personal Data Protection Act


class RegulationFramework:
    """Framework for multi-country compliance rules"""
    
    # Region to regulations mapping
    REGION_REGULATIONS = {
        "EU": [Regulation.GDPR],
        "US": [Regulation.CCPA],
        "CA": [Regulation.CCPA],  # California
        "CN": [Regulation.PIPL],
        "TH": [Regulation.PDPA],
        "BR": [Regulation.LGPD],
        "ZA": [Regulation.POPIA],
        "AU": [Regulation.APRA],
        "CA_FEDERAL": [Regulation.PIPEDA],
        "TR": [Regulation.KVKK],
        "SG": [Regulation.PDPL],
    }
    
    # Regulation requirements
    REGULATION_REQUIREMENTS = {
        Regulation.GDPR: {
            "consent_required": True,
            "data_minimization": True,
            "right_to_deletion": True,
            "right_to_access": True,
            "data_portability": True,
            "breach_notification_days": 72,
            "dpia_required": True,
            "dpo_required": True,
            "max_retention_years": 7,
        },
        Regulation.CCPA: {
            "consent_required": True,
            "data_minimization": True,
            "right_to_deletion": True,
            "right_to_access": True,
            "data_portability": True,
            "breach_notification_days": 30,
            "dpia_required": False,
            "dpo_required": False,
            "max_retention_years": 1,
        },
        Regulation.PIPL: {
            "consent_required": True,
            "data_minimization": True,
            "right_to_deletion": True,
            "right_to_access": True,
            "data_portability": False,
            "breach_notification_days": 30,
            "dpia_required": True,
            "dpo_required": True,
            "max_retention_years": 3,
        },
        Regulation.PDPA: {
            "consent_required": True,
            "data_minimization": True,
            "right_to_deletion": True,
            "right_to_access": True,
            "data_portability": False,
            "breach_notification_days": 30,
            "dpia_required": False,
            "dpo_required": False,
            "max_retention_years": 5,
        },
        Regulation.LGPD: {
            "consent_required": True,
            "data_minimization": True,
            "right_to_deletion": True,
            "right_to_access": True,
            "data_portability": True,
            "breach_notification_days": 30,
            "dpia_required": True,
            "dpo_required": True,
            "max_retention_years": 5,
        },
        Regulation.POPIA: {
            "consent_required": True,
            "data_minimization": True,
            "right_to_deletion": True,
            "right_to_access": True,
            "data_portability": False,
            "breach_notification_days": 30,
            "dpia_required": False,
            "dpo_required": True,
            "max_retention_years": 5,
        },
        Regulation.APRA: {
            "consent_required": True,
            "data_minimization": True,
            "right_to_deletion": True,
            "right_to_access": True,
            "data_portability": False,
            "breach_notification_days": 30,
            "dpia_required": False,
            "dpo_required": False,
            "max_retention_years": 7,
        },
        Regulation.PIPEDA: {
            "consent_required": True,
            "data_minimization": True,
            "right_to_deletion": True,
            "right_to_access": True,
            "data_portability": False,
            "breach_notification_days": 30,
            "dpia_required": False,
            "dpo_required": False,
            "max_retention_years": 7,
        },
        Regulation.KVKK: {
            "consent_required": True,
            "data_minimization": True,
            "right_to_deletion": True,
            "right_to_access": True,
            "data_portability": True,
            "breach_notification_days": 30,
            "dpia_required": False,
            "dpo_required": True,
            "max_retention_years": 5,
        },
        Regulation.PDPL: {
            "consent_required": True,
            "data_minimization": True,
            "right_to_deletion": True,
            "right_to_access": True,
            "data_portability": True,
            "breach_notification_days": 30,
            "dpia_required": False,
            "dpo_required": True,
            "max_retention_years": 5,
        },
    }
    
    @classmethod
    def get_regulations_for_region(cls, region_code: str) -> List[Regulation]:
        """Get applicable regulations for a region"""
        return cls.REGION_REGULATIONS.get(region_code, [])
    
    @classmethod
    def get_regulation_requirements(cls, regulation: Regulation) -> Dict[str, Any]:
        """Get requirements for a specific regulation"""
        return cls.REGULATION_REQUIREMENTS.get(regulation, {})
    
    @classmethod
    def get_strictest_requirements(
        cls, 
        regulations: List[Regulation]
    ) -> Dict[str, Any]:
        """
        Get the strictest requirements across multiple regulations.
        Used when a user is in multiple jurisdictions.
        """
        if not regulations:
            return {}
        
        requirements = {}
        
        for regulation in regulations:
            req = cls.get_regulation_requirements(regulation)
            
            for key, value in req.items():
                if key not in requirements:
                    requirements[key] = value
                else:
                    # Boolean fields: True is stricter
                    if isinstance(value, bool):
                        requirements[key] = requirements[key] or value
                    # Numeric fields: smaller (sooner) is stricter
                    elif isinstance(value, int):
                        requirements[key] = min(requirements[key], value)
        
        return requirements
    
    @classmethod
    def check_violation(
        cls,
        action: str,
        regulation: Regulation,
        details: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Check if an action violates a specific regulation.
        
        Args:
            action: Action type (e.g., 'data_access', 'data_deletion', 'consent_check')
            regulation: Regulation to check against
            details: Additional details about the action
        """
        details = details or {}
        requirement = cls.get_regulation_requirements(regulation)
        violation = False
        reason = ""
        
        if action == "data_access":
            if requirement.get("right_to_access"):
                violation = details.get("access_time_days", 0) > 30
                reason = "Access request not responded within 30 days"
        
        elif action == "data_deletion":
            if requirement.get("right_to_deletion"):
                violation = details.get("deletion_time_days", 0) > 30
                reason = "Deletion request not completed within 30 days"
        
        elif action == "consent":
            if requirement.get("consent_required"):
                violation = not details.get("has_explicit_consent", False)
                reason = "Explicit consent required but not obtained"
        
        elif action == "breach_notification":
            violation = details.get("notification_time_days", 0) > requirement.get("breach_notification_days", 30)
            reason = f"Breach notification exceeded {requirement.get('breach_notification_days')} day limit"
        
        elif action == "data_retention":
            max_years = requirement.get("max_retention_years", 7)
            violation = details.get("retention_years", 0) > max_years
            reason = f"Data retention exceeds {max_years} year limit"
        
        elif action == "dpia":
            if requirement.get("dpia_required"):
                violation = not details.get("has_dpia", False)
                reason = "Data Protection Impact Assessment required but not completed"
        
        return {
            "violation": violation,
            "reason": reason,
            "regulation": regulation.value,
            "action": action,
        }


class ComplianceChecker:
    """Check events for multi-country compliance"""
    
    def __init__(self):
        self.violation_log = []
    
    def evaluate_event_compliance(
        self,
        user_id: str,
        event_type: str,
        region: str,
        event_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate an event against all applicable regulations.
        """
        regulations = RegulationFramework.get_regulations_for_region(region)
        
        violations = []
        risk_score = 0.0
        
        for regulation in regulations:
            # Determine action based on event type
            action = self._map_event_to_action(event_type)
            
            if action:
                result = RegulationFramework.check_violation(
                    action,
                    regulation,
                    event_details
                )
                
                if result["violation"]:
                    violations.append(result)
                    risk_score += 0.5
        
        risk_score = min(1.0, risk_score)
        
        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "applicable_regulations": [r.value for r in regulations],
            "compliance_risk_score": risk_score,
        }
    
    def _map_event_to_action(self, event_type: str) -> str:
        """Map event type to compliance action"""
        mapping = {
            "user_data_access": "data_access",
            "user_data_deletion": "data_deletion",
            "user_consent_change": "consent",
            "breach_detected": "breach_notification",
            "data_export": "data_portability",
        }
        return mapping.get(event_type)
    
    def get_regulation_summary(self, regulations: List[str]) -> Dict[str, Any]:
        """Get summary of regulations"""
        reg_objs = [Regulation[r] for r in regulations if r in Regulation.__members__]
        
        return {
            "regulations": [r.value for r in reg_objs],
            "strictest_requirements": RegulationFramework.get_strictest_requirements(reg_objs),
            "total_requirements": len(RegulationFramework.REGULATION_REQUIREMENTS),
        }


# Global instance
compliance_checker = ComplianceChecker()

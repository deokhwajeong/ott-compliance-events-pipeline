"""Multi-country compliance regulations support"""

import logging
from enum import Enum
from typing import Any, Dict, List

from .dsr import get_deadline

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
    APPI = "APPI"  # Japan - Act on the Protection of Personal Information


class RegulationFramework:
    """Framework for multi-country compliance rules"""

    # Region to regulations mapping. Region codes are ISO 3166 country codes,
    # plus "EU" for traffic that is only known to be EU-originated. US traffic
    # is checked against CCPA as the strictest common US state baseline.
    REGION_REGULATIONS = {
        "EU": [Regulation.GDPR],
        **{
            cc: [Regulation.GDPR]
            for cc in (
                "AT",
                "BE",
                "BG",
                "HR",
                "CY",
                "CZ",
                "DK",
                "EE",
                "FI",
                "FR",
                "DE",
                "GR",
                "HU",
                "IE",
                "IT",
                "LV",
                "LT",
                "LU",
                "MT",
                "NL",
                "PL",
                "PT",
                "RO",
                "SK",
                "SI",
                "ES",
                "SE",
            )
        },
        "US": [Regulation.CCPA],
        "CA": [Regulation.PIPEDA],  # Canada (ISO code), not California
        "CN": [Regulation.PIPL],
        "TH": [Regulation.PDPA],
        "BR": [Regulation.LGPD],
        "ZA": [Regulation.POPIA],
        "AU": [Regulation.APRA],
        "TR": [Regulation.KVKK],
        "SG": [Regulation.PDPL],
        "JP": [Regulation.APPI],
    }

    # Regulation requirements
    REGULATION_REQUIREMENTS = {
        Regulation.GDPR: {
            "consent_required": True,
            "data_minimization": True,
            "right_to_deletion": True,
            "right_to_access": True,
            "data_portability": True,
            # Art. 33(1): notify the supervisory authority within 72 hours.
            "breach_notification_days": 3,
            "dpia_required": True,
            "dpo_required": True,
            "max_retention_years": 7,
        },
        Regulation.CCPA: {
            # CCPA/CPRA is an opt-out regime: no prior consent for ordinary
            # processing, but opt-out signals (e.g. GPC) must be honored for
            # sale/sharing, which includes cross-context behavioral ads.
            "consent_required": False,
            "honor_opt_out_signals": True,
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
        # APPI is not an opt-in regime for ordinary processing: a business may
        # use personal information within the purpose of use it specified and
        # published (Arts. 17, 18, 21). Prior consent is required to provide
        # personal data to a third party (Art. 27(1)), and a provider of
        # "personally referable information" (e.g. cookie or device-level
        # viewing data) must confirm the recipient obtained the person's
        # consent when the recipient will link it to personal data (Art. 31).
        # Article numbers follow the Act as amended in 2020/2021, in force
        # April 2022. No fixed maximum retention period is set, so the key is
        # left out instead of inventing one.
        Regulation.APPI: {
            "consent_required": False,
            "third_party_consent_required": True,
            "data_minimization": False,
            "right_to_deletion": True,
            "right_to_access": True,
            "data_portability": False,
            # PPC Enforcement Rules Art. 8: preliminary report promptly, final
            # report within 30 days (60 days for leaks caused for a wrongful
            # purpose). The 30-day figure is modeled.
            "breach_notification_days": 30,
            "dpia_required": False,
            "dpo_required": False,
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
    def get_strictest_requirements(cls, regulations: List[Regulation]) -> Dict[str, Any]:
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
        cls, action: str, regulation: Regulation, details: Dict[str, Any] = None
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

        if action in ("data_access", "data_deletion"):
            # Per-regulation response periods live in dsr.py with their
            # statutory citations. This day-count form is a quick check; the
            # DSR tracker uses exact calendar dates (GDPR counts in months).
            request_type = "access" if action == "data_access" else "deletion"
            if requirement.get(f"right_to_{request_type}"):
                rule = get_deadline(regulation.value, request_type)
                allowed = rule.nominal_days
                if details.get("extended") and rule.extension:
                    allowed += rule.extension * 30 if rule.extension_unit == "months" else rule.extension
                violation = details.get(f"{request_type}_time_days", 0) > allowed
                period = f"{rule.period} {rule.unit}" if rule.unit == "months" else f"{allowed} days"
                kind = "statutory" if rule.statutory else "policy"
                reason = (
                    f"{request_type.capitalize()} request not completed within {period} "
                    f"({kind} deadline, {rule.citation})"
                )

        elif action == "consent":
            if requirement.get("consent_required"):
                violation = not details.get("has_explicit_consent", False)
                reason = "Explicit consent required but not obtained"

        elif action == "breach_notification":
            violation = details.get("notification_time_days", 0) > requirement.get(
                "breach_notification_days", 30
            )
            reason = f"Breach notification exceeded {requirement.get('breach_notification_days')} day limit"

        elif action == "data_retention":
            max_years = requirement.get("max_retention_years", 7)
            violation = details.get("retention_years", 0) > max_years
            reason = f"Data retention exceeds {max_years} year limit"

        elif action == "ad_targeting":
            if requirement.get("honor_opt_out_signals"):
                violation = bool(details.get("gpc_signal")) and bool(details.get("targeted_ad"))
                reason = "Targeted ad served despite a Global Privacy Control opt-out signal"
            elif requirement.get("consent_required"):
                violation = bool(details.get("targeted_ad")) and not details.get(
                    "has_explicit_consent", False
                )
                reason = "Targeted ad served without consent"
            elif requirement.get("third_party_consent_required"):
                violation = (
                    bool(details.get("targeted_ad"))
                    and bool(details.get("third_party_share"))
                    and not details.get("has_explicit_consent", False)
                )
                reason = "Viewing data shared with a third-party ad partner without consent"

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
        self, user_id: str, event_type: str, region: str, event_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate an event against all applicable regulations.
        """
        regulations = RegulationFramework.get_regulations_for_region(region)

        violations = []
        risk_score = 0.0

        # Determine action based on event type
        action = self._map_event_to_action(event_type)

        for regulation in regulations:
            if action:
                result = RegulationFramework.check_violation(action, regulation, event_details)

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
            # Viewing and session events: processing of personal data that
            # needs consent where the regulation requires opt-in consent
            "play": "consent",
            "pause": "consent",
            "stop": "consent",
            "seek": "consent",
            "login": "consent",
            # Ad events: targeting rules (consent or opt-out, per regulation)
            "ad_impression": "ad_targeting",
            # Data subject requests (dsr_*) are not mapped here: their
            # deadlines depend on time, so dsr.py tracks them as requests.
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

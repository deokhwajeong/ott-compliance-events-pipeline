"""Compliance ROI and cost-benefit analysis"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class ComplianceCost(str, Enum):
    """Types of compliance costs"""
    FINES_AVOIDED = "fines_avoided"
    REPUTATION_PROTECTED = "reputation_protected"
    CUSTOMER_RETENTION = "customer_retention"
    LEGAL_FEES_SAVED = "legal_fees_saved"


class ComplianceExpense(str, Enum):
    """Types of compliance expenses"""
    SYSTEM_INFRASTRUCTURE = "system_infrastructure"
    ML_MODELS = "ml_models"
    TEAM_SALARY = "team_salary"
    TRAINING_EDUCATION = "training_education"
    AUDIT_ASSESSMENT = "audit_assessment"


class ComplianceROICalculator:
    """Calculate ROI of compliance monitoring system"""
    
    # Average fine amounts by regulation (in USD)
    FINE_AMOUNTS = {
        "GDPR": 20_000_000,  # 4% of revenue or €20M
        "CCPA": 7_500,  # Per violation
        "PIPL": 10_000_000,  # Variable
        "PDPA": 1_000_000,  # Variable
        "LGPD": 50_000_000,  # Variable
        "POPIA": 500_000,  # Variable
        "APRA": 2_200_000,  # Variable
        "PIPEDA": 100_000,  # Per violation
        "KVKK": 3_000_000,  # Variable
        "PDPL": 1_000_000,  # Variable
    }
    
    # Customer lifetime value impacts
    IMPACT_LOSS_PER_INCIDENT = {
        "low": 10_000,  # Low severity incident
        "medium": 100_000,  # Medium severity
        "high": 1_000_000,  # High severity
        "critical": 10_000_000,  # Critical incident (data breach)
    }
    
    def __init__(self):
        self.costs: Dict[str, List[Dict]] = {
            "expenses": [],
            "savings": [],
        }
        self.monthly_expenses = {}
        self.monthly_savings = {}
    
    def add_expense(
        self,
        expense_type: str,
        amount: float,
        description: str,
        frequency: str = "monthly"  # monthly, annual, one-time
    ) -> None:
        """Add a compliance expense"""
        expense = {
            "type": expense_type,
            "amount": amount,
            "description": description,
            "frequency": frequency,
            "date": datetime.utcnow().isoformat(),
        }
        self.costs["expenses"].append(expense)
        
        # Convert to monthly for calculation
        if frequency == "monthly":
            monthly = amount
        elif frequency == "annual":
            monthly = amount / 12
        else:  # one-time
            monthly = amount / 12  # Amortize over a year
        
        self.monthly_expenses[expense_type] = self.monthly_expenses.get(expense_type, 0) + monthly
    
    def add_savings(
        self,
        savings_type: str,
        amount: float,
        description: str,
        frequency: str = "monthly",
        incident_count: int = None
    ) -> None:
        """Add compliance-related savings"""
        savings = {
            "type": savings_type,
            "amount": amount,
            "description": description,
            "frequency": frequency,
            "incident_count": incident_count,
            "date": datetime.utcnow().isoformat(),
        }
        self.costs["savings"].append(savings)
        
        # Convert to monthly
        if frequency == "monthly":
            monthly = amount
        elif frequency == "annual":
            monthly = amount / 12
        else:  # incident-based
            monthly = amount if incident_count is None else amount * incident_count
        
        self.monthly_savings[savings_type] = self.monthly_savings.get(savings_type, 0) + monthly
    
    def calculate_prevented_fines(
        self,
        violations_detected: int,
        violations_prevented: int,
        regulation: str
    ) -> Dict[str, Any]:
        """Calculate fines that were prevented"""
        fine_per_violation = self.FINE_AMOUNTS.get(regulation, 1_000_000)
        prevented_fines = violations_prevented * fine_per_violation
        
        # Add risk mitigation from early detection
        early_detection_benefit = violations_detected * (fine_per_violation * 0.1)
        
        return {
            "regulation": regulation,
            "violations_prevented": violations_prevented,
            "prevented_fines": prevented_fines,
            "early_detection_benefit": early_detection_benefit,
            "total_value": prevented_fines + early_detection_benefit,
        }
    
    def calculate_reputation_protection(
        self,
        total_users: int,
        average_customer_lifetime_value: float,
        incidents_prevented: int,
        incident_severity: str = "medium"
    ) -> Dict[str, Any]:
        """Calculate value of reputation protection"""
        # Average percentage of customers who churn after incident
        churn_rates = {
            "low": 0.02,
            "medium": 0.05,
            "high": 0.15,
            "critical": 0.40,
        }
        
        churn_rate = churn_rates.get(incident_severity, 0.05)
        customers_at_risk = total_users * churn_rate
        
        # Value saved per prevented incident
        value_per_incident = customers_at_risk * average_customer_lifetime_value
        total_value = value_per_incident * incidents_prevented
        
        return {
            "customers_protected": int(customers_at_risk),
            "value_per_incident": value_per_incident,
            "incidents_prevented": incidents_prevented,
            "total_protection_value": total_value,
        }
    
    def calculate_legal_savings(
        self,
        incidents_prevented: int,
        average_legal_cost_per_incident: float = 500_000
    ) -> Dict[str, Any]:
        """Calculate legal costs avoided"""
        return {
            "incidents_prevented": incidents_prevented,
            "average_cost_per_incident": average_legal_cost_per_incident,
            "total_legal_savings": incidents_prevented * average_legal_cost_per_incident,
        }
    
    def calculate_roi(
        self,
        time_period_months: int = 12
    ) -> Dict[str, Any]:
        """Calculate overall ROI"""
        total_monthly_expenses = sum(self.monthly_expenses.values())
        total_monthly_savings = sum(self.monthly_savings.values())
        
        period_expenses = total_monthly_expenses * time_period_months
        period_savings = total_monthly_savings * time_period_months
        
        net_benefit = period_savings - period_expenses
        roi_percent = (net_benefit / period_expenses * 100) if period_expenses > 0 else 0
        payback_months = period_expenses / total_monthly_savings if total_monthly_savings > 0 else float('inf')
        
        return {
            "time_period_months": time_period_months,
            "total_expenses": period_expenses,
            "total_savings": period_savings,
            "net_benefit": net_benefit,
            "roi_percent": roi_percent,
            "payback_months": min(payback_months, time_period_months),
            "monthly_breakdown": {
                "expenses": self.monthly_expenses,
                "savings": self.monthly_savings,
            }
        }
    
    def generate_roi_report(
        self,
        violations_detected: int,
        violations_prevented: int,
        incidents_prevented: int,
        total_users: int = 100_000,
        customer_lifetime_value: float = 500,
        time_period_months: int = 12,
        applicable_regulations: List[str] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive ROI report"""
        applicable_regulations = applicable_regulations or ["GDPR", "CCPA"]
        
        # Calculate individual components
        fine_prevention = {}
        total_fine_prevention = 0
        
        for regulation in applicable_regulations:
            result = self.calculate_prevented_fines(
                violations_detected,
                violations_prevented,
                regulation
            )
            fine_prevention[regulation] = result
            total_fine_prevention += result["total_value"]
        
        reputation_protection = self.calculate_reputation_protection(
            total_users,
            customer_lifetime_value,
            incidents_prevented,
            "medium"
        )
        
        legal_savings = self.calculate_legal_savings(incidents_prevented)
        roi = self.calculate_roi(time_period_months)
        
        # Add calculated savings to running total
        self.add_savings(
            ComplianceCost.FINES_AVOIDED.value,
            total_fine_prevention,
            f"Prevented fines across {len(applicable_regulations)} regulations",
            frequency="annual"
        )
        
        self.add_savings(
            ComplianceCost.REPUTATION_PROTECTED.value,
            reputation_protection["total_protection_value"],
            f"Customer retention and reputation protection",
            frequency="annual"
        )
        
        self.add_savings(
            ComplianceCost.LEGAL_FEES_SAVED.value,
            legal_savings["total_legal_savings"],
            f"Legal costs avoided from {incidents_prevented} prevented incidents",
            frequency="annual"
        )
        
        # Recalculate with all savings
        roi = self.calculate_roi(time_period_months)
        
        return {
            "report_date": datetime.utcnow().isoformat(),
            "time_period_months": time_period_months,
            "metrics": {
                "violations_detected": violations_detected,
                "violations_prevented": violations_prevented,
                "incidents_prevented": incidents_prevented,
                "total_users_protected": total_users,
            },
            "fine_prevention": fine_prevention,
            "reputation_protection": reputation_protection,
            "legal_savings": legal_savings,
            "financial_summary": {
                "total_value_protected": (
                    total_fine_prevention + 
                    reputation_protection["total_protection_value"] + 
                    legal_savings["total_legal_savings"]
                ),
                "system_cost": roi["total_expenses"],
                "net_benefit": roi["net_benefit"],
                "roi_percent": roi["roi_percent"],
                "payback_period_months": roi["payback_months"],
            },
            "monthly_breakdown": roi["monthly_breakdown"],
        }
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get summary of all costs and savings"""
        total_expenses = sum(sum(exp["amount"] for exp in self.costs["expenses"]))
        total_savings = sum(sum(sav["amount"] for sav in self.costs["savings"]))
        
        return {
            "total_expenses": total_expenses,
            "total_savings": total_savings,
            "net_benefit": total_savings - total_expenses,
            "expense_breakdown": self.costs["expenses"],
            "savings_breakdown": self.costs["savings"],
        }


# Global instance
roi_calculator = ComplianceROICalculator()

# Default expense setup
roi_calculator.add_expense(
    ComplianceExpense.SYSTEM_INFRASTRUCTURE.value,
    5_000,
    "Cloud infrastructure, database, monitoring",
    frequency="monthly"
)

roi_calculator.add_expense(
    ComplianceExpense.ML_MODELS.value,
    2_000,
    "Model training and maintenance",
    frequency="monthly"
)

roi_calculator.add_expense(
    ComplianceExpense.TEAM_SALARY.value,
    30_000,
    "Compliance team (1 FTE)",
    frequency="monthly"
)

roi_calculator.add_expense(
    ComplianceExpense.TRAINING_EDUCATION.value,
    1_000,
    "Compliance training and certifications",
    frequency="monthly"
)

roi_calculator.add_expense(
    ComplianceExpense.AUDIT_ASSESSMENT.value,
    5_000,
    "Annual audit and assessment",
    frequency="annual"
)

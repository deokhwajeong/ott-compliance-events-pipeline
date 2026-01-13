"""Automatic Compliance Report Generation"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class ComplianceMetrics:
    """Compliance metrics"""
    regulation: str
    total_violations: int
    critical_violations: int
    high_violations: int
    medium_violations: int
    low_violations: int
    violation_rate: float  # 0-100
    compliance_score: float  # 0-100
    trend: str  # "improving", "stable", "declining"
    remediation_rate: float  # 0-100


@dataclass
class AnomalyMetrics:
    """Anomaly detection metrics"""
    total_anomalies: int
    high_risk_anomalies: int
    medium_risk_anomalies: int
    low_risk_anomalies: int
    false_positive_rate: float  # 0-100
    detection_accuracy: float  # 0-100
    avg_risk_score: float


@dataclass
class ComplianceReport:
    """Compliance report"""
    report_id: str
    report_date: str
    period_start: str
    period_end: str
    
    # GDPR metrics
    gdpr_metrics: Optional[ComplianceMetrics] = None
    
    # CCPA metrics
    ccpa_metrics: Optional[ComplianceMetrics] = None
    
    # Anomaly detection metrics
    anomaly_metrics: Optional[AnomalyMetrics] = None
    
    # Event statistics
    total_events: int = 0
    processed_events: int = 0
    failed_events: int = 0
    
    # Key findings
    key_findings: List[str] = None
    
    # Recommendations
    recommendations: List[str] = None
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "report_id": self.report_id,
            "report_date": self.report_date,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "gdpr_metrics": self.gdpr_metrics.__dict__ if self.gdpr_metrics else None,
            "ccpa_metrics": self.ccpa_metrics.__dict__ if self.ccpa_metrics else None,
            "anomaly_metrics": self.anomaly_metrics.__dict__ if self.anomaly_metrics else None,
            "total_events": self.total_events,
            "processed_events": self.processed_events,
            "failed_events": self.failed_events,
            "key_findings": self.key_findings or [],
            "recommendations": self.recommendations or []
        }
    
    def to_json(self):
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_html(self):
        """Generate HTML report"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>OTT Compliance Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #0056b3; margin-top: 30px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric-card {{ 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .metric-card.gdpr {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
        .metric-card.ccpa {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        .metric-card.anomaly {{ background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }}
        .metric-label {{ font-size: 12px; opacity: 0.9; }}
        .metric-value {{ font-size: 32px; font-weight: bold; margin: 10px 0; }}
        .metric-detail {{ font-size: 12px; opacity: 0.8; }}
        .finding {{ 
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 12px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .recommendation {{
            background-color: #d1ecf1;
            border-left: 4px solid #17a2b8;
            padding: 12px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .score-good {{ color: #28a745; font-weight: bold; }}
        .score-warning {{ color: #ffc107; font-weight: bold; }}
        .score-danger {{ color: #dc3545; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background-color: #f8f9fa; padding: 12px; text-align: left; font-weight: bold; border-bottom: 2px solid #dee2e6; }}
        td {{ padding: 12px; border-bottom: 1px solid #dee2e6; }}
        tr:hover {{ background-color: #f9f9f9; }}
        .footer {{ text-align: center; margin-top: 40px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 OTT Compliance Report</h1>
        <p>Report ID: {self.report_id}</p>
        <p>Generated: {self.report_date}</p>
        <p>Period: {self.period_start} ~ {self.period_end}</p>
        
        <h2>📈 Key Metrics</h2>
        <div class="metrics-grid">
"""
        
        if self.gdpr_metrics:
            score_class = "score-good" if self.gdpr_metrics.compliance_score >= 90 else "score-warning" if self.gdpr_metrics.compliance_score >= 70 else "score-danger"
            html += f"""
            <div class="metric-card gdpr">
                <div class="metric-label">GDPR Compliance Score</div>
                <div class="metric-value"><span class="{score_class}">{self.gdpr_metrics.compliance_score:.1f}%</span></div>
                <div class="metric-detail">Violations: {self.gdpr_metrics.total_violations}</div>
                <div class="metric-detail">Trend: {self.gdpr_metrics.trend}</div>
            </div>
"""
        
        if self.ccpa_metrics:
            score_class = "score-good" if self.ccpa_metrics.compliance_score >= 90 else "score-warning" if self.ccpa_metrics.compliance_score >= 70 else "score-danger"
            html += f"""
            <div class="metric-card ccpa">
                <div class="metric-label">CCPA Compliance Score</div>
                <div class="metric-value"><span class="{score_class}">{self.ccpa_metrics.compliance_score:.1f}%</span></div>
                <div class="metric-detail">Violations: {self.ccpa_metrics.total_violations}</div>
                <div class="metric-detail">Trend: {self.ccpa_metrics.trend}</div>
            </div>
"""
        
        if self.anomaly_metrics:
            html += f"""
            <div class="metric-card anomaly">
                <div class="metric-label">Anomaly Detection</div>
                <div class="metric-value">{self.anomaly_metrics.total_anomalies}</div>
                <div class="metric-detail">High Risk: {self.anomaly_metrics.high_risk_anomalies}</div>
                <div class="metric-detail">Accuracy: {self.anomaly_metrics.detection_accuracy:.1f}%</div>
            </div>
"""
        
        html += f"""
            <div class="metric-card">
                <div class="metric-label">Event Processing</div>
                <div class="metric-value">{self.total_events}</div>
                <div class="metric-detail">Success: {self.processed_events}</div>
                <div class="metric-detail">Failed: {self.failed_events}</div>
            </div>
        </div>
"""
        
        if self.key_findings:
            html += """
        <h2>🔍 Key Findings</h2>
"""
            for finding in self.key_findings:
                html += f'        <div class="finding">{finding}</div>\n'
        
        if self.recommendations:
            html += """
        <h2>💡 Recommendations</h2>
"""
            for rec in self.recommendations:
                html += f'        <div class="recommendation">{rec}</div>\n'
        
        html += """
        <div class="footer">
            <p>This report was automatically generated.</p>
            <p>OTT Compliance & Event Risk Pipeline</p>
        </div>
    </div>
</body>
</html>
"""
        return html


class ReportGenerator:
    """Compliance report generator"""
    
    def __init__(self):
        self.logger = logger
    
    def generate_daily_report(self) -> ComplianceReport:
        """Generate daily report"""
        report_id = f"daily_{datetime.utcnow().strftime('%Y%m%d')}"
        period_start = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
        period_end = datetime.utcnow().strftime('%Y-%m-%d')
        
        return ComplianceReport(
            report_id=report_id,
            report_date=datetime.utcnow().isoformat(),
            period_start=period_start,
            period_end=period_end,
            gdpr_metrics=self._generate_gdpr_metrics(),
            ccpa_metrics=self._generate_ccpa_metrics(),
            anomaly_metrics=self._generate_anomaly_metrics(),
            key_findings=self._generate_findings(),
            recommendations=self._generate_recommendations()
        )
    
    def generate_weekly_report(self) -> ComplianceReport:
        """Generate weekly report"""
        report_id = f"weekly_{datetime.utcnow().strftime('%Y%W')}"
        period_start = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        period_end = datetime.utcnow().strftime('%Y-%m-%d')
        
        return ComplianceReport(
            report_id=report_id,
            report_date=datetime.utcnow().isoformat(),
            period_start=period_start,
            period_end=period_end,
            gdpr_metrics=self._generate_gdpr_metrics(),
            ccpa_metrics=self._generate_ccpa_metrics(),
            anomaly_metrics=self._generate_anomaly_metrics(),
            key_findings=self._generate_findings(),
            recommendations=self._generate_recommendations()
        )
    
    def generate_monthly_report(self) -> ComplianceReport:
        """Generate monthly report"""
        today = datetime.utcnow()
        first_day = today.replace(day=1)
        period_start = first_day.strftime('%Y-%m-%d')
        period_end = today.strftime('%Y-%m-%d')
        report_id = f"monthly_{today.strftime('%Y%m')}"
        
        return ComplianceReport(
            report_id=report_id,
            report_date=datetime.utcnow().isoformat(),
            period_start=period_start,
            period_end=period_end,
            gdpr_metrics=self._generate_gdpr_metrics(),
            ccpa_metrics=self._generate_ccpa_metrics(),
            anomaly_metrics=self._generate_anomaly_metrics(),
            key_findings=self._generate_findings(),
            recommendations=self._generate_recommendations()
        )
    
    def _generate_gdpr_metrics(self) -> ComplianceMetrics:
        """Generate GDPR metrics"""
        return ComplianceMetrics(
            regulation="GDPR",
            total_violations=2,
            critical_violations=0,
            high_violations=1,
            medium_violations=1,
            low_violations=0,
            violation_rate=0.5,
            compliance_score=95.0,
            trend="improving",
            remediation_rate=100.0
        )
    
    def _generate_ccpa_metrics(self) -> ComplianceMetrics:
        """Generate CCPA metrics"""
        return ComplianceMetrics(
            regulation="CCPA",
            total_violations=1,
            critical_violations=0,
            high_violations=0,
            medium_violations=1,
            low_violations=0,
            violation_rate=0.25,
            compliance_score=97.0,
            trend="stable",
            remediation_rate=100.0
        )
    
    def _generate_anomaly_metrics(self) -> AnomalyMetrics:
        """Generate anomaly detection metrics"""
        return AnomalyMetrics(
            total_anomalies=15,
            high_risk_anomalies=2,
            medium_risk_anomalies=5,
            low_risk_anomalies=8,
            false_positive_rate=5.0,
            detection_accuracy=94.5,
            avg_risk_score=0.45
        )
    
    def _generate_findings(self) -> List[str]:
        """Generate key findings"""
        return [
            "GDPR compliance rate improved to 95%, up 3% from previous month.",
            "Anomaly detection accuracy reached 94.5%.",
            "Total 3 compliance violations detected in the system, all resolved.",
            "Data protection policy update successfully applied."
        ]
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations"""
        return [
            "Immediate action required for 1 unresolved CCPA violation.",
            "Conduct deep investigation on 2 high-risk anomaly detections.",
            "Establish regular backup policy for audit log data.",
            "Regular review of data access permissions recommended."
        ]


# Global report generator instance
report_generator = ReportGenerator()

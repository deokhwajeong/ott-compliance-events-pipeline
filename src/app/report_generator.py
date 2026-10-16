"""Automatic Compliance Report Generation"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

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
    violation_rate: float  # % of processed events in this regulation's markets
    compliance_score: float  # 100 - violation_rate
    trend: str  # vs the previous period of equal length: improving/stable/declining/n/a
    events_in_scope: int = 0


@dataclass
class AnomalyMetrics:
    """Anomaly detection metrics"""

    total_anomalies: int
    high_risk_anomalies: int
    medium_risk_anomalies: int
    low_risk_anomalies: int
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
            "recommendations": self.recommendations or [],
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
            score_class = (
                "score-good"
                if self.gdpr_metrics.compliance_score >= 90
                else "score-warning"
                if self.gdpr_metrics.compliance_score >= 70
                else "score-danger"
            )
            html += f"""
            <div class="metric-card gdpr">
                <div class="metric-label">GDPR Compliance Score</div>
                <div class="metric-value"><span class="{score_class}">{self.gdpr_metrics.compliance_score:.1f}%</span></div>
                <div class="metric-detail">Violations: {self.gdpr_metrics.total_violations}</div>
                <div class="metric-detail">Trend: {self.gdpr_metrics.trend}</div>
            </div>
"""

        if self.ccpa_metrics:
            score_class = (
                "score-good"
                if self.ccpa_metrics.compliance_score >= 90
                else "score-warning"
                if self.ccpa_metrics.compliance_score >= 70
                else "score-danger"
            )
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
                <div class="metric-detail">Avg risk score: {self.anomaly_metrics.avg_risk_score:.1f}</div>
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
    """Builds compliance reports from processed events stored in the database."""

    def __init__(self):
        self.logger = logger

    def generate_daily_report(self, db) -> ComplianceReport:
        now = datetime.utcnow()
        return self._build(db, f"daily_{now.strftime('%Y%m%d')}", now - timedelta(days=1), now)

    def generate_weekly_report(self, db) -> ComplianceReport:
        now = datetime.utcnow()
        return self._build(db, f"weekly_{now.strftime('%Y%W')}", now - timedelta(days=7), now)

    def generate_monthly_report(self, db) -> ComplianceReport:
        now = datetime.utcnow()
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return self._build(db, f"monthly_{now.strftime('%Y%m')}", start, now)

    # ------------------------------------------------------------------

    def _rows(self, db, start: datetime, end: datetime):
        from .models import ProcessedEvent, RawEvent

        rows = (
            db.query(ProcessedEvent, RawEvent)
            .join(RawEvent, RawEvent.event_id == ProcessedEvent.event_id)
            .filter(ProcessedEvent.processed_at >= start, ProcessedEvent.processed_at <= end)
            .all()
        )
        return [(p.risk_level, p.risk_score or 0.0, json.loads(p.flags or "[]"), r.region) for p, r in rows]

    def _regulation_metrics(self, regulation: str, rows, previous_rows) -> ComplianceMetrics:
        from .regulations import RegulationFramework

        def in_scope(region):
            return regulation in [r.value for r in RegulationFramework.get_regulations_for_region(region)]

        def rate(data):
            scoped = [row for row in data if in_scope(row[3])]
            bad = [row for row in scoped if any(f.startswith(regulation.lower() + "_") for f in row[2])]
            return scoped, bad, (100.0 * len(bad) / len(scoped)) if scoped else 0.0

        scoped, bad, violation_rate = rate(rows)
        prev_scoped, _, prev_rate = rate(previous_rows)
        if not scoped or not prev_scoped:
            trend = "n/a"
        elif violation_rate < prev_rate - 1:
            trend = "improving"
        elif violation_rate > prev_rate + 1:
            trend = "declining"
        else:
            trend = "stable"

        return ComplianceMetrics(
            regulation=regulation,
            total_violations=len(bad),
            critical_violations=0,
            high_violations=sum(1 for row in bad if row[0] == "high"),
            medium_violations=sum(1 for row in bad if row[0] == "medium"),
            low_violations=sum(1 for row in bad if row[0] == "low"),
            violation_rate=round(violation_rate, 2),
            compliance_score=round(100.0 - violation_rate, 2),
            trend=trend,
            events_in_scope=len(scoped),
        )

    def _anomaly_metrics(self, rows) -> AnomalyMetrics:
        anomalies = [row for row in rows if "ml_ensemble_anomaly" in row[2]]
        return AnomalyMetrics(
            total_anomalies=len(anomalies),
            high_risk_anomalies=sum(1 for row in anomalies if row[0] == "high"),
            medium_risk_anomalies=sum(1 for row in anomalies if row[0] == "medium"),
            low_risk_anomalies=sum(1 for row in anomalies if row[0] == "low"),
            avg_risk_score=round(sum(row[1] for row in anomalies) / len(anomalies), 2) if anomalies else 0.0,
        )

    def _build(self, db, report_id: str, start: datetime, end: datetime) -> ComplianceReport:
        rows = self._rows(db, start, end)
        previous_rows = self._rows(db, start - (end - start), start)
        gdpr = self._regulation_metrics("GDPR", rows, previous_rows)
        ccpa = self._regulation_metrics("CCPA", rows, previous_rows)
        anomaly = self._anomaly_metrics(rows)
        high = sum(1 for row in rows if row[0] == "high")

        findings = [
            f"{len(rows)} events processed in the period; {high} rated high risk.",
            f"GDPR: {gdpr.total_violations} violations across {gdpr.events_in_scope} events in scope "
            f"({gdpr.violation_rate:.1f}%).",
            f"CCPA: {ccpa.total_violations} violations across {ccpa.events_in_scope} events in scope "
            f"({ccpa.violation_rate:.1f}%).",
            f"{anomaly.total_anomalies} events carried the anomaly-detector flag.",
        ]
        recommendations = []
        if gdpr.total_violations:
            recommendations.append("Review consent collection in GDPR markets with flagged playback events.")
        if ccpa.total_violations:
            recommendations.append("Check that the ad stack honors Global Privacy Control signals.")
        if anomaly.high_risk_anomalies:
            recommendations.append("Investigate high-risk events that the anomaly detector also flagged.")

        return ComplianceReport(
            report_id=report_id,
            report_date=datetime.utcnow().isoformat(),
            period_start=start.strftime("%Y-%m-%d"),
            period_end=end.strftime("%Y-%m-%d"),
            gdpr_metrics=gdpr,
            ccpa_metrics=ccpa,
            anomaly_metrics=anomaly,
            total_events=len(rows),
            processed_events=len(rows),
            failed_events=0,
            key_findings=findings,
            recommendations=recommendations,
        )


# Global report generator instance
report_generator = ReportGenerator()

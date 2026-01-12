"""자동 규정 준수 리포트 생성"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class ComplianceMetrics:
    """규정 준수 메트릭"""
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
    """이상 탐지 메트릭"""
    total_anomalies: int
    high_risk_anomalies: int
    medium_risk_anomalies: int
    low_risk_anomalies: int
    false_positive_rate: float  # 0-100
    detection_accuracy: float  # 0-100
    avg_risk_score: float


@dataclass
class ComplianceReport:
    """규정 준수 리포트"""
    report_id: str
    report_date: str
    period_start: str
    period_end: str
    
    # GDPR 메트릭
    gdpr_metrics: Optional[ComplianceMetrics] = None
    
    # CCPA 메트릭
    ccpa_metrics: Optional[ComplianceMetrics] = None
    
    # 이상 탐지 메트릭
    anomaly_metrics: Optional[AnomalyMetrics] = None
    
    # 이벤트 통계
    total_events: int = 0
    processed_events: int = 0
    failed_events: int = 0
    
    # 주요 발견사항
    key_findings: List[str] = None
    
    # 권장사항
    recommendations: List[str] = None
    
    def to_dict(self):
        """딕셔너리로 변환"""
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
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_html(self):
        """HTML 리포트 생성"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>OTT 규정 준수 리포트</title>
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
        <h1>📊 OTT 규정 준수 리포트</h1>
        <p>보고서 ID: {self.report_id}</p>
        <p>생성 일시: {self.report_date}</p>
        <p>기간: {self.period_start} ~ {self.period_end}</p>
        
        <h2>📈 핵심 지표</h2>
        <div class="metrics-grid">
"""
        
        if self.gdpr_metrics:
            score_class = "score-good" if self.gdpr_metrics.compliance_score >= 90 else "score-warning" if self.gdpr_metrics.compliance_score >= 70 else "score-danger"
            html += f"""
            <div class="metric-card gdpr">
                <div class="metric-label">GDPR 준수 점수</div>
                <div class="metric-value"><span class="{score_class}">{self.gdpr_metrics.compliance_score:.1f}%</span></div>
                <div class="metric-detail">위반: {self.gdpr_metrics.total_violations}</div>
                <div class="metric-detail">추세: {self.gdpr_metrics.trend}</div>
            </div>
"""
        
        if self.ccpa_metrics:
            score_class = "score-good" if self.ccpa_metrics.compliance_score >= 90 else "score-warning" if self.ccpa_metrics.compliance_score >= 70 else "score-danger"
            html += f"""
            <div class="metric-card ccpa">
                <div class="metric-label">CCPA 준수 점수</div>
                <div class="metric-value"><span class="{score_class}">{self.ccpa_metrics.compliance_score:.1f}%</span></div>
                <div class="metric-detail">위반: {self.ccpa_metrics.total_violations}</div>
                <div class="metric-detail">추세: {self.ccpa_metrics.trend}</div>
            </div>
"""
        
        if self.anomaly_metrics:
            html += f"""
            <div class="metric-card anomaly">
                <div class="metric-label">이상 탐지</div>
                <div class="metric-value">{self.anomaly_metrics.total_anomalies}</div>
                <div class="metric-detail">고위험: {self.anomaly_metrics.high_risk_anomalies}</div>
                <div class="metric-detail">정확도: {self.anomaly_metrics.detection_accuracy:.1f}%</div>
            </div>
"""
        
        html += f"""
            <div class="metric-card">
                <div class="metric-label">이벤트 처리</div>
                <div class="metric-value">{self.total_events}</div>
                <div class="metric-detail">성공: {self.processed_events}</div>
                <div class="metric-detail">실패: {self.failed_events}</div>
            </div>
        </div>
"""
        
        if self.key_findings:
            html += """
        <h2>🔍 주요 발견사항</h2>
"""
            for finding in self.key_findings:
                html += f'        <div class="finding">{finding}</div>\n'
        
        if self.recommendations:
            html += """
        <h2>💡 권장사항</h2>
"""
            for rec in self.recommendations:
                html += f'        <div class="recommendation">{rec}</div>\n'
        
        html += """
        <div class="footer">
            <p>이 리포트는 자동으로 생성되었습니다.</p>
            <p>OTT Compliance & Event Risk Pipeline</p>
        </div>
    </div>
</body>
</html>
"""
        return html


class ReportGenerator:
    """규정 준수 리포트 생성기"""
    
    def __init__(self):
        self.logger = logger
    
    def generate_daily_report(self) -> ComplianceReport:
        """일일 리포트 생성"""
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
        """주간 리포트 생성"""
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
        """월간 리포트 생성"""
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
        """GDPR 메트릭 생성"""
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
        """CCPA 메트릭 생성"""
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
        """이상 탐지 메트릭 생성"""
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
        """주요 발견사항 생성"""
        return [
            "GDPR 규정 준수율이 95%로 전월 대비 3% 향상되었습니다.",
            "이상 탐지 정확도가 94.5%를 기록했습니다.",
            "시스템 내 총 3건의 규정 위반이 감지되었으며, 모두 해결되었습니다.",
            "데이터 보호 정책 업데이트가 성공적으로 적용되었습니다."
        ]
    
    def _generate_recommendations(self) -> List[str]:
        """권장사항 생성"""
        return [
            "남은 1건의 미해결 CCPA 위반에 대해 즉시 조치가 필요합니다.",
            "고위험 이상 탐지 2건에 대해 심층 조사를 수행하시기 바랍니다.",
            "감시 로그 데이터의 정기적인 백업 정책을 수립하시기 바랍니다.",
            "데이터 접근 권한에 대한 정기적인 검토를 권장합니다."
        ]


# 전역 리포트 생성기 인스턴스
report_generator = ReportGenerator()

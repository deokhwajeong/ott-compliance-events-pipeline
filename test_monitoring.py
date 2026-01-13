#!/usr/bin/env python3
"""Prometheus + Audit Log + Report Generation Integration Test"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.metrics import MetricsRecorder
from app.audit_log import audit_logger, AuditAction, ActorRole
from app.report_generator import report_generator
from datetime import datetime


def main():
    print("=" * 70)
    print("OTT Compliance Pipeline - Prometheus + Audit Log + Report Integration Test")
    print("=" * 70)
    
    # 1. Record metrics
    print("\n[1] Prometheus Metrics Recording]")
    MetricsRecorder.record_event("watch", "user_001")
    MetricsRecorder.record_event("login", "user_002")
    MetricsRecorder.record_event_processed("watch", "success")
    MetricsRecorder.record_event_processed("login", "success")
    print("✓ Event metrics recording complete")
    
    MetricsRecorder.record_anomaly("unusual_activity", 0.87, "high")
    MetricsRecorder.record_anomaly("bulk_download", 0.65, "medium")
    print("✓ Anomaly detection metrics recording complete")
    
    MetricsRecorder.record_violation("GDPR", "data_retention_exceeded", "high")
    MetricsRecorder.record_violation("CCPA", "consent_not_obtained", "medium")
    MetricsRecorder.update_compliance_score("GDPR", 95.0)
    MetricsRecorder.update_compliance_score("CCPA", 97.0)
    print("✓ Compliance metrics recording complete")
    
    # 2. Audit log
    print("\n[2] Audit Log Recording]")
    audit_logger.log_data_access(
        actor_id="admin_001",
        target_user_id="user_001",
        resource="user_profile"
    )
    print("✓ Data access log recorded")
    
    audit_logger.log_data_export(
        actor_id="admin_001",
        target_user_id="user_001",
        export_format="json"
    )
    print("✓ Data export log recorded")
    
    audit_logger.log_compliance_check(
        actor_id="auditor_001",
        regulation="GDPR",
        result="compliant",
        details={"checked_items": 45, "violations": 0}
    )
    print("✓ Compliance check log recorded")
    
    audit_logger.log_violation(
        actor_id="system",
        violation_type="excessive_data_retention",
        severity="high",
        regulation="GDPR"
    )
    print("✓ Violation log recorded")
    
    # 3. Auto report generation
    print("\n[3] Auto Compliance Report Generation]")
    
    daily_report = report_generator.generate_daily_report()
    print(f"✓ Daily report generated (ID: {daily_report.report_id})")
    print(f"  - GDPR compliance score: {daily_report.gdpr_metrics.compliance_score}%")
    print(f"  - CCPA compliance score: {daily_report.ccpa_metrics.compliance_score}%")
    print(f"  - Anomalies detected: {daily_report.anomaly_metrics.total_anomalies} items")
    
    weekly_report = report_generator.generate_weekly_report()
    print(f"✓ Weekly report generated (ID: {weekly_report.report_id})")
    
    monthly_report = report_generator.generate_monthly_report()
    print(f"✓ Monthly report generated (ID: {monthly_report.report_id})")
    
    # 4. Print sample report content
    print("\n[4] Daily Report Summary]")
    print(f"Period: {daily_report.period_start} ~ {daily_report.period_end}")
    print(f"Total events: {daily_report.total_events}")
    print("\nKey findings:")
    for finding in daily_report.key_findings or []:
        print(f"  - {finding}")
    
    print("\nRecommendations:")
    for rec in daily_report.recommendations or []:
        print(f"  - {rec}")
    
    # 5. Save HTML report
    print("\n[5] HTML Report Generation]")
    html_content = daily_report.to_html()
    report_path = Path(__file__).parent / "daily_report.html"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"✓ HTML report saved: {report_path}")
    
    # 6. Save JSON report
    json_report_path = Path(__file__).parent / "daily_report.json"
    with open(json_report_path, 'w', encoding='utf-8') as f:
        f.write(daily_report.to_json())
    print(f"✓ JSON report saved: {json_report_path}")
    
    print("\n" + "=" * 70)
    print("✓ All tests complete!")
    print("\nMonitoring Dashboards:")
    print("  - Prometheus: http://localhost:9090")
    print("  - Grafana: http://localhost:3000 (admin/admin)")
    print("  - Kafka UI: http://localhost:8080")
    print("\nAPI Endpoints:")
    print("  - Metrics: http://localhost:8000/metrics")
    print("  - Daily report: http://localhost:8000/api/v1/reports/daily")
    print("  - Weekly report: http://localhost:8000/api/v1/reports/weekly")
    print("  - Monthly report: http://localhost:8000/api/v1/reports/monthly")
    print("  - Audit logs: http://localhost:8000/api/v1/audit/log")
    print("=" * 70)


if __name__ == "__main__":
    main()

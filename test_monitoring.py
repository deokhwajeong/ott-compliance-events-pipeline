#!/usr/bin/env python3
"""Prometheus + 감시 로그 + 리포트 생성 통합 테스트"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.metrics import MetricsRecorder
from app.audit_log import audit_logger, AuditAction, ActorRole
from app.report_generator import report_generator
from datetime import datetime


def main():
    print("=" * 70)
    print("OTT Compliance Pipeline - Prometheus + 감시 로그 + 리포트 통합 테스트")
    print("=" * 70)
    
    # 1. 메트릭 기록
    print("\n[1️⃣  Prometheus 메트릭 기록]")
    MetricsRecorder.record_event("watch", "user_001")
    MetricsRecorder.record_event("login", "user_002")
    MetricsRecorder.record_event_processed("watch", "success")
    MetricsRecorder.record_event_processed("login", "success")
    print("✓ 이벤트 메트릭 기록 완료")
    
    MetricsRecorder.record_anomaly("unusual_activity", 0.87, "high")
    MetricsRecorder.record_anomaly("bulk_download", 0.65, "medium")
    print("✓ 이상 탐지 메트릭 기록 완료")
    
    MetricsRecorder.record_violation("GDPR", "data_retention_exceeded", "high")
    MetricsRecorder.record_violation("CCPA", "consent_not_obtained", "medium")
    MetricsRecorder.update_compliance_score("GDPR", 95.0)
    MetricsRecorder.update_compliance_score("CCPA", 97.0)
    print("✓ 규정 준수 메트릭 기록 완료")
    
    # 2. 감시 로그
    print("\n[2️⃣  감시 로그 기록]")
    audit_logger.log_data_access(
        actor_id="admin_001",
        target_user_id="user_001",
        resource="user_profile"
    )
    print("✓ 데이터 접근 로그 기록")
    
    audit_logger.log_data_export(
        actor_id="admin_001",
        target_user_id="user_001",
        export_format="json"
    )
    print("✓ 데이터 내보내기 로그 기록")
    
    audit_logger.log_compliance_check(
        actor_id="auditor_001",
        regulation="GDPR",
        result="compliant",
        details={"checked_items": 45, "violations": 0}
    )
    print("✓ 규정 준수 검사 로그 기록")
    
    audit_logger.log_violation(
        actor_id="system",
        violation_type="excessive_data_retention",
        severity="high",
        regulation="GDPR"
    )
    print("✓ 규정 위반 로그 기록")
    
    # 3. 자동 리포트 생성
    print("\n[3️⃣  자동 규정 준수 리포트 생성]")
    
    daily_report = report_generator.generate_daily_report()
    print(f"✓ 일일 리포트 생성 (ID: {daily_report.report_id})")
    print(f"  - GDPR 준수점수: {daily_report.gdpr_metrics.compliance_score}%")
    print(f"  - CCPA 준수점수: {daily_report.ccpa_metrics.compliance_score}%")
    print(f"  - 이상 탐지: {daily_report.anomaly_metrics.total_anomalies}건")
    
    weekly_report = report_generator.generate_weekly_report()
    print(f"✓ 주간 리포트 생성 (ID: {weekly_report.report_id})")
    
    monthly_report = report_generator.generate_monthly_report()
    print(f"✓ 월간 리포트 생성 (ID: {monthly_report.report_id})")
    
    # 4. 리포트 내용 샘플 출력
    print("\n[4️⃣  일일 리포트 요약]")
    print(f"기간: {daily_report.period_start} ~ {daily_report.period_end}")
    print(f"총 이벤트: {daily_report.total_events}")
    print("\n주요 발견사항:")
    for finding in daily_report.key_findings or []:
        print(f"  - {finding}")
    
    print("\n권장사항:")
    for rec in daily_report.recommendations or []:
        print(f"  - {rec}")
    
    # 5. HTML 리포트 저장
    print("\n[5️⃣  HTML 리포트 생성]")
    html_content = daily_report.to_html()
    report_path = Path(__file__).parent / "daily_report.html"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"✓ HTML 리포트 저장: {report_path}")
    
    # 6. JSON 리포트 저장
    json_report_path = Path(__file__).parent / "daily_report.json"
    with open(json_report_path, 'w', encoding='utf-8') as f:
        f.write(daily_report.to_json())
    print(f"✓ JSON 리포트 저장: {json_report_path}")
    
    print("\n" + "=" * 70)
    print("✓ 모든 테스트 완료!")
    print("\n📊 모니터링 대시보드:")
    print("  - Prometheus: http://localhost:9090")
    print("  - Grafana: http://localhost:3000 (admin/admin)")
    print("  - Kafka UI: http://localhost:8080")
    print("\n📋 API 엔드포인트:")
    print("  - 메트릭: http://localhost:8000/metrics")
    print("  - 일일 리포트: http://localhost:8000/api/v1/reports/daily")
    print("  - 주간 리포트: http://localhost:8000/api/v1/reports/weekly")
    print("  - 월간 리포트: http://localhost:8000/api/v1/reports/monthly")
    print("  - 감시 로그: http://localhost:8000/api/v1/audit/log")
    print("=" * 70)


if __name__ == "__main__":
    main()

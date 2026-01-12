#!/usr/bin/env python3
"""Kafka 통합 테스트 스크립트"""

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

# 경로 설정
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.queue import Event, ComplianceEventQueue
from app.kafka_config import kafka_settings
from app.kafka_manager import kafka_manager


async def main():
    print("=" * 60)
    print("OTT Compliance Pipeline - Kafka 통합 테스트")
    print("=" * 60)
    
    # Kafka 프로듀서 초기화
    await kafka_manager.init_producer()
    print(f"✓ Kafka Producer 초기화 완료 (Brokers: {kafka_settings.bootstrap_servers})")
    print(f"✓ 토픽 설정: {kafka_settings.topics}")
    
    # 테스트 이벤트 생성
    queue = ComplianceEventQueue(use_kafka=True)
    
    test_events = [
        Event(
            event_id=str(uuid.uuid4()),
            user_id="user_123",
            device_id="tv_001",
            event_type="watch",
            payload={"title": "Breaking Bad", "duration": 3600}
        ),
        Event(
            event_id=str(uuid.uuid4()),
            user_id="user_456",
            device_id="tv_002",
            event_type="login",
            payload={"ip": "192.168.1.1", "device_model": "Samsung"}
        ),
        Event(
            event_id=str(uuid.uuid4()),
            user_id="user_123",
            device_id="mobile_001",
            event_type="purchase",
            payload={"items": ["season_pass"], "amount": 99.99}
        ),
    ]
    
    # 이벤트 발행
    print("\n[이벤트 발행]")
    for event in test_events:
        success = await queue.enqueue_event(event)
        status = "✓" if success else "✗"
        print(f"{status} {event.event_type.upper():10} | User: {event.user_id:10} | Device: {event.device_id}")
    
    # 이상 탐지 시뮬레이션
    print("\n[이상 탐지 알림]")
    anomaly = {
        "user_id": "user_123",
        "anomaly_type": "unusual_activity",
        "risk_score": 0.87,
        "timestamp": datetime.utcnow().isoformat()
    }
    await queue.enqueue_anomaly(anomaly)
    print(f"✓ 이상 탐지 발행됨 (Risk Score: {anomaly['risk_score']})")
    
    # 규정 위반 기록
    print("\n[GDPR 규정 위반]")
    violation = {
        "user_id": "user_456",
        "violation_type": "excessive_data_retention",
        "severity": "high",
        "timestamp": datetime.utcnow().isoformat()
    }
    await queue.enqueue_compliance_violation(violation)
    print(f"✓ 규정 위반 기록됨 (Severity: {violation['severity']})")
    
    # 감시 로그
    print("\n[감시 로그]")
    audit = {
        "action": "data_export",
        "actor": "admin_001",
        "target_user": "user_123",
        "timestamp": datetime.utcnow().isoformat()
    }
    await queue.enqueue_audit_log(audit)
    print(f"✓ 감시 로그 기록됨 (Action: {audit['action']})")
    
    # 정리
    await kafka_manager.close()
    
    print("\n" + "=" * 60)
    print("✓ 테스트 완료!")
    print(f"  Kafka UI: http://localhost:8080")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Kafka Integration Test Script"""

import asyncio
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Path configuration
sys.path.insert(0, str(Path(__file__).parent / "src"))

from app.queue import Event, ComplianceEventQueue
from app.kafka_config import kafka_settings
from app.kafka_manager import kafka_manager


async def main():
    print("=" * 60)
    print("OTT Compliance Pipeline - Kafka Integration Test")
    print("=" * 60)
    
    # Kafka Producer initialization
    await kafka_manager.init_producer()
    print(f"✓ Kafka Producer initialized (Brokers: {kafka_settings.bootstrap_servers})")
    print(f"✓ Topics: {kafka_settings.topics}")
    
    # Create test events
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
    
    # Event publishing
    print("\n[Event Publishing]")
    for event in test_events:
        success = await queue.enqueue_event(event)
        status = "✓" if success else "✗"
        print(f"{status} {event.event_type.upper():10} | User: {event.user_id:10} | Device: {event.device_id}")
    
    # Anomaly detection simulation
    print("\n[Anomaly Detection Alert]")
    anomaly = {
        "user_id": "user_123",
        "anomaly_type": "unusual_activity",
        "risk_score": 0.87,
        "timestamp": datetime.utcnow().isoformat()
    }
    await queue.enqueue_anomaly(anomaly)
    print(f"✓ Anomaly published (Risk Score: {anomaly['risk_score']})")
    
    # Compliance violation record
    print("\n[GDPR Compliance Violation]")
    violation = {
        "user_id": "user_456",
        "violation_type": "excessive_data_retention",
        "severity": "high",
        "timestamp": datetime.utcnow().isoformat()
    }
    await queue.enqueue_compliance_violation(violation)
    print(f"✓ Compliance violation recorded (Severity: {violation['severity']})")
    
    # Audit log
    print("\n[Audit Log]")
    audit = {
        "action": "data_export",
        "actor": "admin_001",
        "target_user": "user_123",
        "timestamp": datetime.utcnow().isoformat()
    }
    await queue.enqueue_audit_log(audit)
    print(f"✓ Audit log recorded (Action: {audit['action']})")
    
    # Cleanup
    await kafka_manager.close()
    
    print("\n" + "=" * 60)
    print("✓ Test completed!")
    print(f"  Kafka UI: http://localhost:8080")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

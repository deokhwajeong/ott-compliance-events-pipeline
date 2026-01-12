import pytest
from src.app.schemas import Event
from src.app.compliance_rules import evaluate_compliance
from src.app.queue import enqueue_event, dequeue_event, stats_snapshot
from src.app.db import SessionLocal, engine
from src.app.models import Base, RawEvent, ProcessedEvent
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Create test database
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()

def test_event_schema():
    event_data = {
        "event_id": "123",
        "user_id": "user1",
        "device_id": "dev1",
        "content_id": "content1",
        "event_type": "play",
        "timestamp": "2023-01-01T00:00:00Z",
        "region": "US",
        "is_eu": False,
        "has_consent": True,
        "ip_address": "192.168.1.1"
    }
    event = Event(**event_data)
    assert event.event_id == "123"

def test_compliance_evaluation():
    event = {
        "event_type": "error",
        "user_id": "user1",
        "device_id": "dev1"
    }
    result = evaluate_compliance(event)
    assert "flags" in result
    assert "risk_level" in result

def test_queue_operations():
    # Clear queue first
    while dequeue_event() is not None:
        pass
    
    enqueue_event({"test": "data"})
    event = dequeue_event()
    assert event == {"test": "data"}
    
    # Check stats
    stats = stats_snapshot()
    assert stats["enqueued"] >= 1

def test_db_save_event(db_session):
    import uuid
    event_data = {
        "event_id": f"db_test_{uuid.uuid4().hex[:8]}",
        "user_id": "user_db",
        "device_id": "dev_db",
        "content_id": "content_db",
        "event_type": "play",
        "timestamp": "2023-01-01T00:00:00Z",
        "region": "US",
        "is_eu": False,
        "has_consent": True,
        "ip_address": "192.168.1.1",
        "subscription_plan": "basic"
    }
    db_event = RawEvent(
        event_id=event_data["event_id"],
        user_id=event_data["user_id"],
        device_id=event_data["device_id"],
        content_id=event_data["content_id"],
        event_type=event_data["event_type"],
        timestamp=datetime.fromisoformat(event_data["timestamp"].replace('Z', '+00:00')),
        region=event_data["region"],
        is_eu=event_data["is_eu"],
        has_consent=event_data["has_consent"],
        ip_address=event_data["ip_address"],
        subscription_plan=event_data["subscription_plan"]
    )
    db_session.add(db_event)
    db_session.commit()
    
    saved = db_session.query(RawEvent).filter(RawEvent.event_id == event_data["event_id"]).first()
    assert saved.user_id == "user_db"
    assert saved.subscription_plan == "basic"

def test_db_save_processed(db_session):
    processed = ProcessedEvent(
        event_id="proc_test",
        risk_score=5.0,
        risk_level="medium",
        flags='["test_flag"]'
    )
    db_session.add(processed)
    db_session.commit()
    
    saved = db_session.query(ProcessedEvent).filter(ProcessedEvent.event_id == "proc_test").first()
    assert saved.risk_level == "medium"
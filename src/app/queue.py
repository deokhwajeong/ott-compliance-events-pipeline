import logging
from typing import Callable, Optional
from datetime import datetime
from dataclasses import dataclass, field
from collections import deque

from .kafka_manager import kafka_manager
from .kafka_config import kafka_settings

logger = logging.getLogger(__name__)

# Fallback: Local in-memory queue when Kafka is not used
_event_queue: deque = deque()

# Statistics
_stats = {
    "enqueued": 0,
    "processed": 0,
    "errors": 0,
    "queue_size": 0
}


@dataclass
class Event:
    """Event model"""
    event_id: str
    user_id: str
    device_id: str
    event_type: str
    payload: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self):
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat()
        }


class ComplianceEventQueue:
    """Kafka-based compliance event queue"""
    
    def __init__(self, use_kafka: bool = False):
        self.kafka = kafka_manager
        self.use_kafka = use_kafka
        self.processed_count = 0
    
    async def enqueue_event(self, event: Event) -> bool:
        """Add event to queue"""
        try:
            if self.use_kafka:
                # Publish to Kafka (partition key: user_id)
                await self.kafka.send_event(
                    topic=kafka_settings.topics["events"],
                    event=event.to_dict(),
                    partition_key=event.user_id
                )
            else:
                # Local fallback
                _event_queue.append(event.to_dict())
                _stats["queue_size"] = len(_event_queue)
            
            _stats["enqueued"] += 1
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue event: {e}")
            _stats["errors"] += 1
            return False
    
    async def enqueue_anomaly(self, anomaly_data: dict) -> bool:
        """Publish anomaly detection results"""
        try:
            if self.use_kafka:
                await self.kafka.send_event(
                    topic=kafka_settings.topics["anomalies"],
                    event=anomaly_data,
                    partition_key=anomaly_data.get("user_id")
                )
            return True
        except Exception as e:
            logger.error(f"Failed to publish anomaly: {e}")
            _stats["errors"] += 1
            return False
    
    async def enqueue_compliance_violation(self, violation: dict) -> bool:
        """Record compliance violation"""
        try:
            if self.use_kafka:
                await self.kafka.send_event(
                    topic=kafka_settings.topics["compliance_violations"],
                    event=violation,
                    partition_key=violation.get("user_id")
                )
            return True
        except Exception as e:
            logger.error(f"Failed to record violation: {e}")
            _stats["errors"] += 1
            return False
    
    async def enqueue_audit_log(self, audit_entry: dict) -> bool:
        """Record audit log"""
        try:
            if self.use_kafka:
                await self.kafka.send_event(
                    topic=kafka_settings.topics["audit_logs"],
                    event=audit_entry,
                    partition_key=None
                )
            return True
        except Exception as e:
            logger.error(f"Failed to record audit log: {e}")
            _stats["errors"] += 1
            return False
    
    async def subscribe_to_events(self, callback: Callable):
        """Subscribe to events"""
        if self.use_kafka:
            await self.kafka.init_consumer(
                topic=kafka_settings.topics["events"],
                callback=callback
            )


# Global queue instance
event_queue = ComplianceEventQueue(use_kafka=False)


# Legacy API compatibility
def enqueue_event(event: dict) -> None:
    """Add an event to the queue."""
    _event_queue.append(event)
    _stats["enqueued"] += 1
    _stats["queue_size"] = len(_event_queue)


def dequeue_event() -> dict | None:
    """Remove and return the next event from the queue."""
    if _event_queue:
        event = _event_queue.popleft()
        _stats["queue_size"] = len(_event_queue)
        return event
    return None


def drain() -> list[dict]:
    """Return all events in the queue and clear it."""
    events = list(_event_queue)
    _event_queue.clear()
    _stats["queue_size"] = 0
    return events


def stats_snapshot() -> dict:
    """Return a snapshot of current statistics."""
    return _stats.copy()


def mark_processed() -> None:
    """Increment processed count."""
    _stats["processed"] += 1


def mark_error() -> None:
    """Increment error count."""
    _stats["errors"] += 1

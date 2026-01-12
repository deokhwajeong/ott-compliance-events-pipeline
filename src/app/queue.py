import logging
from typing import Callable, Optional
from datetime import datetime
from dataclasses import dataclass, field
from collections import deque

from .kafka_manager import kafka_manager
from .kafka_config import kafka_settings

logger = logging.getLogger(__name__)

# 폴백: Kafka 미사용 시 로컬 메모리 큐
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
    """이벤트 모델"""
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
    """Kafka 기반 규정 준수 이벤트 큐"""
    
    def __init__(self, use_kafka: bool = False):
        self.kafka = kafka_manager
        self.use_kafka = use_kafka
        self.processed_count = 0
    
    async def enqueue_event(self, event: Event) -> bool:
        """이벤트 큐에 추가"""
        try:
            if self.use_kafka:
                # Kafka로 발행 (파티션 키: user_id)
                await self.kafka.send_event(
                    topic=kafka_settings.topics["events"],
                    event=event.to_dict(),
                    partition_key=event.user_id
                )
            else:
                # 로컬 폴백
                _event_queue.append(event.to_dict())
                _stats["queue_size"] = len(_event_queue)
            
            _stats["enqueued"] += 1
            return True
        except Exception as e:
            logger.error(f"이벤트 큐 실패: {e}")
            _stats["errors"] += 1
            return False
    
    async def enqueue_anomaly(self, anomaly_data: dict) -> bool:
        """이상 탐지 결과 발행"""
        try:
            if self.use_kafka:
                await self.kafka.send_event(
                    topic=kafka_settings.topics["anomalies"],
                    event=anomaly_data,
                    partition_key=anomaly_data.get("user_id")
                )
            return True
        except Exception as e:
            logger.error(f"이상 발행 실패: {e}")
            _stats["errors"] += 1
            return False
    
    async def enqueue_compliance_violation(self, violation: dict) -> bool:
        """규정 위반 기록"""
        try:
            if self.use_kafka:
                await self.kafka.send_event(
                    topic=kafka_settings.topics["compliance_violations"],
                    event=violation,
                    partition_key=violation.get("user_id")
                )
            return True
        except Exception as e:
            logger.error(f"위반 기록 실패: {e}")
            _stats["errors"] += 1
            return False
    
    async def enqueue_audit_log(self, audit_entry: dict) -> bool:
        """감시 로그 기록"""
        try:
            if self.use_kafka:
                await self.kafka.send_event(
                    topic=kafka_settings.topics["audit_logs"],
                    event=audit_entry,
                    partition_key=None
                )
            return True
        except Exception as e:
            logger.error(f"감시 로그 실패: {e}")
            _stats["errors"] += 1
            return False
    
    async def subscribe_to_events(self, callback: Callable):
        """이벤트 구독"""
        if self.use_kafka:
            await self.kafka.init_consumer(
                topic=kafka_settings.topics["events"],
                callback=callback
            )


# 전역 큐 인스턴스
event_queue = ComplianceEventQueue(use_kafka=False)


# 레거시 API 호환성
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

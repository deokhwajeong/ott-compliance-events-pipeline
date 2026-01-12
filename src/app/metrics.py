"""Prometheus 메트릭 정의"""

from prometheus_client import Counter, Histogram, Gauge
import time

# 이벤트 메트릭
events_received = Counter(
    'ott_events_received_total',
    'OTT 이벤트 수신 총개수',
    ['event_type', 'user_id']
)

events_processed = Counter(
    'ott_events_processed_total',
    'OTT 이벤트 처리 총개수',
    ['event_type', 'status']
)

event_processing_time = Histogram(
    'ott_event_processing_seconds',
    'OTT 이벤트 처리 시간',
    ['event_type'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0)
)

# 이상 탐지 메트릭
anomalies_detected = Counter(
    'ott_anomalies_detected_total',
    '탐지된 이상 총개수',
    ['anomaly_type', 'severity']
)

anomaly_risk_score = Histogram(
    'ott_anomaly_risk_score',
    '이상 탐지 리스크 점수',
    ['anomaly_type'],
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
)

# 규정 준수 메트릭
compliance_violations = Counter(
    'ott_compliance_violations_total',
    '규정 위반 총개수',
    ['regulation', 'violation_type', 'severity']
)

compliance_score = Gauge(
    'ott_compliance_score',
    '규정 준수 점수 (0-100)',
    ['regulation']
)

# Kafka 메트릭
kafka_messages_sent = Counter(
    'ott_kafka_messages_sent_total',
    'Kafka 발행 메시지 총개수',
    ['topic']
)

kafka_messages_consumed = Counter(
    'ott_kafka_messages_consumed_total',
    'Kafka 소비 메시지 총개수',
    ['topic']
)

kafka_consumer_lag = Gauge(
    'ott_kafka_consumer_lag',
    'Kafka 컨슈머 지연',
    ['topic', 'partition']
)

# 감시 로그 메트릭
audit_logs_recorded = Counter(
    'ott_audit_logs_recorded_total',
    '기록된 감시 로그 총개수',
    ['action', 'actor_role']
)

# API 성능 메트릭
http_request_duration = Histogram(
    'ott_http_request_seconds',
    'HTTP 요청 처리 시간',
    ['method', 'endpoint', 'status'],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

http_requests_total = Counter(
    'ott_http_requests_total',
    'HTTP 요청 총개수',
    ['method', 'endpoint', 'status']
)

# 데이터베이스 메트릭
db_query_duration = Histogram(
    'ott_db_query_seconds',
    '데이터베이스 쿼리 실행 시간',
    ['query_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5)
)

db_connection_pool_size = Gauge(
    'ott_db_connection_pool_size',
    '데이터베이스 연결 풀 크기',
)

# 큐 메트릭
queue_size = Gauge(
    'ott_queue_size',
    '큐 크기',
    ['queue_name']
)

queue_enqueue_duration = Histogram(
    'ott_queue_enqueue_seconds',
    '큐 추가 시간',
    ['queue_name'],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1)
)


class MetricsRecorder:
    """메트릭 기록 헬퍼"""
    
    @staticmethod
    def record_event(event_type: str, user_id: str = "unknown"):
        """이벤트 수신 기록"""
        events_received.labels(event_type=event_type, user_id=user_id).inc()
    
    @staticmethod
    def record_event_processed(event_type: str, status: str = "success"):
        """이벤트 처리 기록"""
        events_processed.labels(event_type=event_type, status=status).inc()
    
    @staticmethod
    def record_anomaly(anomaly_type: str, risk_score: float, severity: str = "medium"):
        """이상 탐지 기록"""
        anomalies_detected.labels(anomaly_type=anomaly_type, severity=severity).inc()
        anomaly_risk_score.labels(anomaly_type=anomaly_type).observe(risk_score)
    
    @staticmethod
    def record_violation(regulation: str, violation_type: str, severity: str = "medium"):
        """규정 위반 기록"""
        compliance_violations.labels(
            regulation=regulation,
            violation_type=violation_type,
            severity=severity
        ).inc()
    
    @staticmethod
    def record_audit_log(action: str, actor_role: str = "admin"):
        """감시 로그 기록"""
        audit_logs_recorded.labels(action=action, actor_role=actor_role).inc()
    
    @staticmethod
    def update_compliance_score(regulation: str, score: float):
        """규정 준수 점수 업데이트"""
        compliance_score.labels(regulation=regulation).set(score)
    
    @staticmethod
    def record_kafka_message(topic: str, direction: str = "send"):
        """Kafka 메시지 기록"""
        if direction == "send":
            kafka_messages_sent.labels(topic=topic).inc()
        else:
            kafka_messages_consumed.labels(topic=topic).inc()

"""Prometheus Metrics Definition"""

from prometheus_client import Counter, Histogram, Gauge
import time

# Event metrics
events_received = Counter(
    'ott_events_received_total',
    'Total OTT events received',
    ['event_type', 'user_id']
)

events_processed = Counter(
    'ott_events_processed_total',
    'Total OTT events processed',
    ['event_type', 'status']
)

event_processing_time = Histogram(
    'ott_event_processing_seconds',
    'OTT event processing time',
    ['event_type'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0)
)

# Anomaly detection metrics
anomalies_detected = Counter(
    'ott_anomalies_detected_total',
    'Total anomalies detected',
    ['anomaly_type', 'severity']
)

anomaly_risk_score = Histogram(
    'ott_anomaly_risk_score',
    'Anomaly detection risk score',
    ['anomaly_type'],
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
)

# Compliance metrics
compliance_violations = Counter(
    'ott_compliance_violations_total',
    'Total compliance violations',
    ['regulation', 'violation_type', 'severity']
)

compliance_score = Gauge(
    'ott_compliance_score',
    'Compliance score (0-100)',
    ['regulation']
)

# Kafka metrics
kafka_messages_sent = Counter(
    'ott_kafka_messages_sent_total',
    'Total Kafka messages published',
    ['topic']
)

kafka_messages_consumed = Counter(
    'ott_kafka_messages_consumed_total',
    'Total Kafka messages consumed',
    ['topic']
)

kafka_consumer_lag = Gauge(
    'ott_kafka_consumer_lag',
    'Kafka consumer lag',
    ['topic', 'partition']
)

# Audit log metrics
audit_logs_recorded = Counter(
    'ott_audit_logs_recorded_total',
    'Total audit logs recorded',
    ['action', 'actor_role']
)

# API performance metrics
http_request_duration = Histogram(
    'ott_http_request_seconds',
    'HTTP request processing time',
    ['method', 'endpoint', 'status'],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

http_requests_total = Counter(
    'ott_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

# Database metrics
db_query_duration = Histogram(
    'ott_db_query_seconds',
    'Database query execution time',
    ['query_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5)
)

db_connection_pool_size = Gauge(
    'ott_db_connection_pool_size',
    'Database connection pool size',
)

# Queue metrics
queue_size = Gauge(
    'ott_queue_size',
    'Queue size',
    ['queue_name']
)

queue_enqueue_duration = Histogram(
    'ott_queue_enqueue_seconds',
    'Queue enqueue time',
    ['queue_name'],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1)
)


class MetricsRecorder:
    """Metrics recording helper"""
    
    @staticmethod
    def record_event(event_type: str, user_id: str = "unknown"):
        """Record event reception"""
        events_received.labels(event_type=event_type, user_id=user_id).inc()
    
    @staticmethod
    def record_event_processed(event_type: str, status: str = "success"):
        """Record event processing"""
        events_processed.labels(event_type=event_type, status=status).inc()
    
    @staticmethod
    def record_anomaly(anomaly_type: str, risk_score: float, severity: str = "medium"):
        """Record anomaly detection"""
        anomalies_detected.labels(anomaly_type=anomaly_type, severity=severity).inc()
        anomaly_risk_score.labels(anomaly_type=anomaly_type).observe(risk_score)
    
    @staticmethod
    def record_violation(regulation: str, violation_type: str, severity: str = "medium"):
        """Record compliance violation"""
        compliance_violations.labels(
            regulation=regulation,
            violation_type=violation_type,
            severity=severity
        ).inc()
    
    @staticmethod
    def record_audit_log(action: str, actor_role: str = "admin"):
        """Record audit log"""
        audit_logs_recorded.labels(action=action, actor_role=actor_role).inc()
    
    @staticmethod
    def update_compliance_score(regulation: str, score: float):
        """Update compliance score"""
        compliance_score.labels(regulation=regulation).set(score)
    
    @staticmethod
    def record_kafka_message(topic: str, direction: str = "send"):
        """Record Kafka message"""
        if direction == "send":
            kafka_messages_sent.labels(topic=topic).inc()
        else:
            kafka_messages_consumed.labels(topic=topic).inc()    
    @staticmethod
    def record_cache_hit(cache_type: str = "redis"):
        """Record cache hit"""
        try:
            cache_hits.labels(cache_type=cache_type).inc()
        except:
            pass  # Metric might not be defined in all configurations
    
    @staticmethod
    def record_cache_miss(cache_type: str = "redis"):
        """Record cache miss"""
        try:
            cache_misses.labels(cache_type=cache_type).inc()
        except:
            pass
    
    @staticmethod
    def record_ml_prediction(model_name: str, accuracy: float):
        """Record ML model prediction accuracy"""
        try:
            ml_model_accuracy.labels(model_name=model_name).set(accuracy)
        except:
            pass


# Optional metrics for advanced monitoring
try:
    cache_hits = Histogram(
        'ott_cache_hits_total',
        'Total cache hits',
        ['cache_type'],
    )
    
    cache_misses = Histogram(
        'ott_cache_misses_total',
        'Total cache misses',
        ['cache_type'],
    )
    
    ml_model_accuracy = Gauge(
        'ott_ml_model_accuracy',
        'ML model accuracy',
        ['model_name'],
    )
except:
    # Already defined
    pass
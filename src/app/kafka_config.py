from pydantic_settings import BaseSettings
from typing import Optional


class KafkaSettings(BaseSettings):
    """Kafka Configuration Settings"""
    bootstrap_servers: list[str] = ["localhost:9092"]
    topics: dict[str, str] = {
        "events": "ott-events",
        "anomalies": "ott-anomalies",
        "compliance_violations": "ott-compliance-violations",
        "audit_logs": "ott-audit-logs"
    }
    consumer_group: str = "ott-compliance-pipeline"
    max_poll_records: int = 500
    session_timeout_ms: int = 30000
    request_timeout_ms: int = 40000
    
    class Config:
        env_file = ".env"
        env_prefix = "KAFKA_"


kafka_settings = KafkaSettings()

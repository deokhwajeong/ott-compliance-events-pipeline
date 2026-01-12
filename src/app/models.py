from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float
from .db import Base

class RawEvent(Base):
    __tablename__ = "raw_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True)
    user_id = Column(String, index=True)
    device_id = Column(String, index=True)
    content_id = Column(String, index=True)
    event_type = Column(String)
    timestamp = Column(DateTime)
    region = Column(String)
    is_eu = Column(Boolean)
    has_consent = Column(Boolean)
    ip_address = Column(String)
    error_code = Column(String, nullable=True)
    extra_metadata = Column(Text, nullable=True)  # JSON string
    subscription_plan = Column(String, nullable=True)

class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, index=True)
    risk_score = Column(Float)
    risk_level = Column(String)  # low, medium, high
    flags = Column(Text)  # JSON string of flags list
    processed_at = Column(DateTime)

class AggregateStats(Base):
    __tablename__ = "aggregate_stats"

    id = Column(Integer, primary_key=True, index=True)
    total_enqueued = Column(Integer, default=0)
    total_processed = Column(Integer, default=0)
    total_errors = Column(Integer, default=0)
    low_risk_count = Column(Integer, default=0)
    medium_risk_count = Column(Integer, default=0)
    high_risk_count = Column(Integer, default=0)
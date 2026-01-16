from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List
from datetime import datetime
import re

class Event(BaseModel):
    event_id: str = Field(..., min_length=1, max_length=255)
    user_id: str = Field(..., min_length=1, max_length=255)
    device_id: str = Field(..., min_length=1, max_length=255)
    content_id: str = Field(..., min_length=1, max_length=255)
    event_type: str = Field(..., min_length=1, max_length=50)
    timestamp: str
    region: str = Field(..., min_length=2, max_length=10)
    is_eu: bool
    has_consent: bool
    ip_address: str
    error_code: Optional[str] = Field(None, max_length=50)
    extra_metadata: Optional[Dict] = None
    subscription_plan: Optional[str] = Field(None, max_length=20)
    
    @validator('event_type')
    def validate_event_type(cls, v):
        valid_types = {
            'play', 'pause', 'stop', 'seek', 'error',
            'login', 'logout', 'login_failed',
            'purchase', 'download', 'export',
            'token_refresh', 'token_refresh_failed',
            'bulk_download', 'access'
        }
        if v not in valid_types:
            raise ValueError(f'Invalid event type: {v}. Must be one of {valid_types}')
        return v
    
    @validator('ip_address')
    def validate_ip(cls, v):
        # Basic IP address validation
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        ipv6_pattern = r'^([0-9a-fA-F]{0,4}:)+[0-9a-fA-F]{0,4}$'
        if not (re.match(ipv4_pattern, v) or re.match(ipv6_pattern, v)):
            raise ValueError(f'Invalid IP address: {v}')
        return v
    
    @validator('timestamp')
    def validate_timestamp(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except:
            raise ValueError(f'Invalid timestamp format: {v}')
        return v


class EventIn(BaseModel):
    """Incoming event schema with strict validation"""
    event_id: str = Field(..., min_length=1, max_length=255)
    user_id: str = Field(..., min_length=1, max_length=255)
    device_id: str = Field(..., min_length=1, max_length=255)
    content_id: str = Field(..., min_length=1, max_length=255)
    event_type: str = Field(..., min_length=1, max_length=50)
    timestamp: str
    region: str = Field(..., min_length=2, max_length=10)
    is_eu: bool
    has_consent: bool
    ip_address: str
    error_code: Optional[str] = Field(None, max_length=50)
    extra_metadata: Optional[Dict] = None
    subscription_plan: Optional[str] = Field(None, max_length=20)
    
    @validator('subscription_plan')
    def validate_subscription(cls, v):
        if v and v not in {'basic', 'premium', 'vip', 'trial'}:
            raise ValueError(f'Invalid subscription plan: {v}')
        return v


class RiskProfile(BaseModel):
    """User risk profile response"""
    user_id: str
    violation_likelihood: float = Field(..., ge=0.0, le=1.0)
    violation_confidence: float = Field(..., ge=0.0, le=1.0)
    risk_factors: List[str] = []
    predicted_regulations: List[tuple] = []
    is_anomaly: bool
    anomaly_score: float = Field(..., ge=0.0, le=1.0)


class ComplianceTrend(BaseModel):
    """Compliance trend data"""
    timestamp: str
    low_risk_count: int
    medium_risk_count: int
    high_risk_count: int


class CacheStats(BaseModel):
    """Cache statistics"""
    status: str
    used_memory_mb: Optional[float] = None
    total_keys: Optional[int] = None
    connected_clients: Optional[int] = None


def validate_event_data(event: Dict) -> tuple[bool, str]:
    """Validate event data comprehensively"""
    required_fields = [
        'event_id', 'user_id', 'device_id', 'content_id',
        'event_type', 'timestamp', 'region', 'ip_address'
    ]
    
    for field in required_fields:
        if field not in event or not event[field]:
            return False, f"Missing required field: {field}"
    
    # Additional validation logic
    if len(str(event.get('event_id', ''))) > 255:
        return False, "event_id too long"
    
    return True, "Valid"

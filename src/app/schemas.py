from pydantic import BaseModel
from typing import Optional, Dict

class Event(BaseModel):
    event_id: str
    user_id: str
    device_id: str
    content_id: str
    event_type: str
    timestamp: str
    region: str
    is_eu: bool
    has_consent: bool
    ip_address: str
    error_code: Optional[str] = None
    extra_metadata: Optional[Dict] = None
    subscription_plan: Optional[str] = None  # New: basic, premium, etc.

class EventIn(BaseModel):
    event_id: str
    user_id: str
    device_id: str
    content_id: str
    event_type: str
    timestamp: str
    region: str
    is_eu: bool
    has_consent: bool
    ip_address: str
    error_code: Optional[str] = None
    extra_metadata: Optional[Dict] = None
    subscription_plan: Optional[str] = None

def risk_score(event):
    if event.get("region") == "EU":
        return "privacy_risk"
    return "low"

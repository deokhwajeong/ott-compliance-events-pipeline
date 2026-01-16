"""
Multi-tenancy Support Module
Provides tenant isolation, data segregation, and per-tenant configuration
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class TenantTier(str, Enum):
    """Tenant subscription tiers"""

    FREE = "free"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class TenantConfig:
    """Configuration for a tenant"""

    TIER_LIMITS = {
        TenantTier.FREE: {
            "max_events_per_day": 10000,
            "max_users": 1,
            "max_api_calls_per_hour": 1000,
            "storage_gb": 1,
            "retention_days": 7,
            "features": ["basic_analytics"],
        },
        TenantTier.STANDARD: {
            "max_events_per_day": 1000000,
            "max_users": 10,
            "max_api_calls_per_hour": 10000,
            "storage_gb": 100,
            "retention_days": 90,
            "features": ["basic_analytics", "ml_models", "custom_alerts"],
        },
        TenantTier.PREMIUM: {
            "max_events_per_day": 10000000,
            "max_users": 100,
            "max_api_calls_per_hour": 100000,
            "storage_gb": 1000,
            "retention_days": 365,
            "features": [
                "basic_analytics",
                "ml_models",
                "custom_alerts",
                "custom_regulations",
                "api_access",
            ],
        },
        TenantTier.ENTERPRISE: {
            "max_events_per_day": None,  # Unlimited
            "max_users": None,
            "max_api_calls_per_hour": None,
            "storage_gb": None,
            "retention_days": None,
            "features": [
                "basic_analytics",
                "ml_models",
                "custom_alerts",
                "custom_regulations",
                "api_access",
                "sso",
                "audit_logs",
                "dedicated_support",
            ],
        },
    }

    def __init__(
        self,
        tenant_id: str,
        name: str,
        tier: TenantTier = TenantTier.STANDARD,
        custom_regulations: Optional[List[str]] = None,
    ):
        self.tenant_id = tenant_id
        self.name = name
        self.tier = tier
        self.custom_regulations = custom_regulations or []
        self.created_at = datetime.utcnow()
        self.config = self.TIER_LIMITS.get(tier, self.TIER_LIMITS[TenantTier.STANDARD])
        self.settings = {
            "data_isolation": True,
            "encryption_enabled": True,
            "audit_logging": True,
            "backup_frequency": "daily" if tier != TenantTier.FREE else "never",
        }

    def has_feature(self, feature: str) -> bool:
        """Check if tenant has access to feature"""
        return feature in self.config.get("features", [])

    def get_limit(self, limit_key: str) -> Optional[int]:
        """Get limit for tenant"""
        return self.config.get(limit_key)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "tier": self.tier,
            "created_at": self.created_at.isoformat(),
            "config": self.config,
            "settings": self.settings,
            "custom_regulations": self.custom_regulations,
        }


class TenantContext:
    """Thread-safe tenant context"""

    def __init__(self, tenant_id: str, tenant_config: TenantConfig):
        self.tenant_id = tenant_id
        self.config = tenant_config
        self.request_id = str(uuid.uuid4())
        self.created_at = datetime.utcnow()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TenantManager:
    """Manage multiple tenants"""

    def __init__(self):
        self.tenants: Dict[str, TenantConfig] = {}
        self.usage: Dict[str, Dict[str, Any]] = {}

    def create_tenant(
        self,
        name: str,
        tier: TenantTier = TenantTier.STANDARD,
        custom_regulations: Optional[List[str]] = None,
    ) -> TenantConfig:
        """Create new tenant"""
        tenant_id = str(uuid.uuid4())
        config = TenantConfig(tenant_id, name, tier, custom_regulations)
        self.tenants[tenant_id] = config
        self.usage[tenant_id] = {
            "events_today": 0,
            "api_calls_this_hour": 0,
            "storage_used_gb": 0,
            "last_reset": datetime.utcnow(),
        }
        logger.info(f"Created tenant {tenant_id} ({name}) with tier {tier}")
        return config

    def get_tenant(self, tenant_id: str) -> Optional[TenantConfig]:
        """Get tenant configuration"""
        return self.tenants.get(tenant_id)

    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete tenant"""
        if tenant_id in self.tenants:
            del self.tenants[tenant_id]
            if tenant_id in self.usage:
                del self.usage[tenant_id]
            logger.info(f"Deleted tenant {tenant_id}")
            return True
        return False

    def check_event_limit(self, tenant_id: str) -> bool:
        """Check if tenant can process more events"""
        config = self.get_tenant(tenant_id)
        if not config:
            return False

        limit = config.get_limit("max_events_per_day")
        if limit is None:  # Unlimited
            return True

        usage = self.usage.get(tenant_id, {})
        return usage.get("events_today", 0) < limit

    def check_api_limit(self, tenant_id: str) -> bool:
        """Check if tenant can make more API calls"""
        config = self.get_tenant(tenant_id)
        if not config:
            return False

        limit = config.get_limit("max_api_calls_per_hour")
        if limit is None:  # Unlimited
            return True

        usage = self.usage.get(tenant_id, {})
        return usage.get("api_calls_this_hour", 0) < limit

    def increment_event_count(self, tenant_id: str):
        """Increment event count for tenant"""
        if tenant_id in self.usage:
            self.usage[tenant_id]["events_today"] += 1

    def increment_api_call_count(self, tenant_id: str):
        """Increment API call count for tenant"""
        if tenant_id in self.usage:
            self.usage[tenant_id]["api_calls_this_hour"] += 1

    def get_usage(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get usage statistics for tenant"""
        return self.usage.get(tenant_id)

    def list_tenants(self) -> Dict[str, TenantConfig]:
        """List all tenants"""
        return self.tenants.copy()


class DataIsolation:
    """Data isolation layer for multi-tenancy"""

    @staticmethod
    def build_tenant_filter(tenant_id: str) -> Dict[str, str]:
        """Build database filter for tenant isolation"""
        return {"tenant_id": tenant_id}

    @staticmethod
    def add_tenant_field(data: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """Add tenant_id field to data"""
        data["tenant_id"] = tenant_id
        return data

    @staticmethod
    def is_tenant_data(data: Dict[str, Any], tenant_id: str) -> bool:
        """Check if data belongs to tenant"""
        return data.get("tenant_id") == tenant_id


class BillingTracker:
    """Track usage and billing for tenants"""

    def __init__(self):
        self.billing_records: Dict[str, List[Dict[str, Any]]] = {}

    def record_usage(
        self, tenant_id: str, resource: str, quantity: float, cost: float
    ):
        """Record resource usage for billing"""
        if tenant_id not in self.billing_records:
            self.billing_records[tenant_id] = []

        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "resource": resource,
            "quantity": quantity,
            "cost": cost,
        }
        self.billing_records[tenant_id].append(record)

    def calculate_monthly_bill(self, tenant_id: str) -> float:
        """Calculate monthly bill for tenant"""
        if tenant_id not in self.billing_records:
            return 0.0

        total_cost = 0.0
        now = datetime.utcnow()
        month_ago = now - timedelta(days=30)

        for record in self.billing_records[tenant_id]:
            record_time = datetime.fromisoformat(record["timestamp"])
            if month_ago <= record_time <= now:
                total_cost += record.get("cost", 0)

        return total_cost

    def get_billing_history(
        self, tenant_id: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get billing history for tenant"""
        if tenant_id not in self.billing_records:
            return []

        history = []
        now = datetime.utcnow()
        cutoff = now - timedelta(days=days)

        for record in self.billing_records[tenant_id]:
            record_time = datetime.fromisoformat(record["timestamp"])
            if cutoff <= record_time <= now:
                history.append(record)

        return sorted(history, key=lambda x: x["timestamp"], reverse=True)


# Global tenant manager instance
_tenant_manager = None


def get_tenant_manager() -> TenantManager:
    """Get global tenant manager instance"""
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
    return _tenant_manager


def get_tenant_context(tenant_id: str) -> Optional[TenantContext]:
    """Get tenant context for request"""
    manager = get_tenant_manager()
    config = manager.get_tenant(tenant_id)
    if config:
        return TenantContext(tenant_id, config)
    return None

"""
API Gateway Integration Module
Provides API Gateway configuration and middleware for Kong/Traefik
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class RateLimitPolicy(str, Enum):
    """Rate limiting policies"""

    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class RateLimitConfig:
    """Rate limiting configuration"""

    POLICIES = {
        RateLimitPolicy.BASIC: {
            "requests_per_minute": 60,
            "burst_size": 10,
            "daily_limit": 50000,
        },
        RateLimitPolicy.STANDARD: {
            "requests_per_minute": 300,
            "burst_size": 50,
            "daily_limit": 500000,
        },
        RateLimitPolicy.PREMIUM: {
            "requests_per_minute": 1000,
            "burst_size": 100,
            "daily_limit": 5000000,
        },
        RateLimitPolicy.ENTERPRISE: {
            "requests_per_minute": 5000,
            "burst_size": 500,
            "daily_limit": None,  # Unlimited
        },
    }


class APIVersion:
    """API versioning management"""

    def __init__(self):
        self.versions = {
            "v1": {
                "deprecated": False,
                "sunset_date": None,
                "endpoints": ["events", "alerts", "metrics"],
            },
            "v2": {
                "deprecated": False,
                "sunset_date": None,
                "endpoints": ["events", "alerts", "metrics", "reports"],
            },
            "v3": {
                "deprecated": False,
                "sunset_date": None,
                "endpoints": [
                    "events",
                    "alerts",
                    "metrics",
                    "reports",
                    "graphql",
                    "websocket",
                ],
            },
        }

    def get_version_info(self, version: str) -> Optional[Dict[str, Any]]:
        """Get version information"""
        return self.versions.get(version)

    def is_deprecated(self, version: str) -> bool:
        """Check if version is deprecated"""
        info = self.get_version_info(version)
        if not info:
            return True
        return info.get("deprecated", False)

    def get_sunset_date(self, version: str) -> Optional[datetime]:
        """Get sunset date for deprecated version"""
        info = self.get_version_info(version)
        if not info:
            return None
        return info.get("sunset_date")


class ServiceMesh:
    """Service mesh configuration for Kubernetes"""

    def __init__(self):
        self.services = {
            "api-service": {
                "port": 8000,
                "instances": 3,
                "health_check": "/health",
                "timeout": 30,
            },
            "kafka-consumer": {
                "port": None,
                "instances": 2,
                "health_check": None,
                "timeout": None,
            },
            "ml-service": {
                "port": 8001,
                "instances": 2,
                "health_check": "/ml/health",
                "timeout": 60,
            },
            "cache-service": {
                "port": 6379,
                "instances": 1,
                "health_check": None,
                "timeout": None,
            },
            "database-service": {
                "port": 5432,
                "instances": 1,
                "health_check": None,
                "timeout": None,
            },
        }

    def get_service_config(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get service configuration"""
        return self.services.get(service_name)

    def list_services(self) -> Dict[str, Dict[str, Any]]:
        """List all services"""
        return self.services


class APIGatewayConfig:
    """API Gateway configuration"""

    def __init__(self):
        self.rate_limit = RateLimitConfig()
        self.versioning = APIVersion()
        self.service_mesh = ServiceMesh()
        self.routes = self._build_routes()
        self.plugins = self._build_plugins()

    def _build_routes(self) -> Dict[str, Dict[str, Any]]:
        """Build API routes configuration"""
        return {
            "/api/v1/events": {
                "upstream": "api-service:8000",
                "methods": ["GET", "POST"],
                "rate_limit": RateLimitPolicy.STANDARD,
                "auth_required": True,
                "timeout": 30,
            },
            "/api/v1/alerts": {
                "upstream": "api-service:8000",
                "methods": ["GET"],
                "rate_limit": RateLimitPolicy.STANDARD,
                "auth_required": True,
                "timeout": 30,
            },
            "/api/v1/metrics": {
                "upstream": "api-service:8000",
                "methods": ["GET"],
                "rate_limit": RateLimitPolicy.BASIC,
                "auth_required": False,
                "timeout": 30,
            },
            "/api/v2/events": {
                "upstream": "api-service:8000",
                "methods": ["GET", "POST"],
                "rate_limit": RateLimitPolicy.PREMIUM,
                "auth_required": True,
                "timeout": 30,
            },
            "/api/v3/graphql": {
                "upstream": "api-service:8000",
                "methods": ["GET", "POST"],
                "rate_limit": RateLimitPolicy.PREMIUM,
                "auth_required": True,
                "timeout": 60,
            },
            "/ws": {
                "upstream": "api-service:8000",
                "methods": ["GET"],
                "rate_limit": None,
                "auth_required": True,
                "timeout": None,  # Keep-alive connection
            },
        }

    def _build_plugins(self) -> Dict[str, Dict[str, Any]]:
        """Build plugin configuration"""
        return {
            "authentication": {
                "enabled": True,
                "type": "jwt",
                "key_claim": "sub",
                "secret_location": "/etc/kong/secrets/jwt-secret",
            },
            "rate-limiting": {
                "enabled": True,
                "redis_host": "cache-service",
                "redis_port": 6379,
            },
            "request-transformer": {
                "enabled": True,
                "add_headers": {
                    "X-Forwarded-By": "api-gateway",
                    "X-Request-ID": "{{request_id}}",
                },
            },
            "response-transformer": {
                "enabled": True,
                "add_headers": {
                    "X-API-Version": "v3",
                    "X-Response-Time": "{{response_time}}",
                },
            },
            "cors": {
                "enabled": True,
                "origins": ["*"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "credentials": True,
                "max_age": 3600,
            },
            "log-enrichment": {
                "enabled": True,
                "add_fields": {
                    "api_version": "{{api_version}}",
                    "user_id": "{{user_id}}",
                    "timestamp": "{{timestamp}}",
                },
            },
        }

    def get_route_config(self, path: str) -> Optional[Dict[str, Any]]:
        """Get route configuration"""
        return self.routes.get(path)

    def get_rate_limit_policy(
        self, path: str
    ) -> Optional[Dict[str, int]]:
        """Get rate limit policy for a route"""
        route = self.get_route_config(path)
        if not route:
            return None

        policy = route.get("rate_limit")
        if policy:
            return self.rate_limit.POLICIES.get(policy)
        return None


class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 2,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # seconds
        self.success_threshold = success_threshold
        self.failures = 0
        self.successes = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = None

    def record_success(self):
        """Record successful request"""
        if self.state == "HALF_OPEN":
            self.successes += 1
            if self.successes >= self.success_threshold:
                self.state = "CLOSED"
                self.failures = 0
                self.successes = 0
                logger.info("Circuit breaker CLOSED")

    def record_failure(self):
        """Record failed request"""
        self.failures += 1
        self.last_failure_time = datetime.utcnow()

        if self.failures >= self.failure_threshold:
            if self.state == "CLOSED":
                self.state = "OPEN"
                logger.warning(f"Circuit breaker OPEN after {self.failures} failures")
            elif self.state == "HALF_OPEN":
                self.state = "OPEN"
                self.successes = 0
                logger.warning("Circuit breaker OPEN (half-open recovery failed)")

    def can_attempt(self) -> bool:
        """Check if request can be attempted"""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            # Check if recovery timeout has passed
            if self.last_failure_time:
                elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    self.failures = 0
                    logger.info("Circuit breaker HALF_OPEN (attempting recovery)")
                    return True
            return False

        # HALF_OPEN
        return True

    def get_state(self) -> str:
        """Get current circuit breaker state"""
        return self.state


def create_kong_config() -> Dict[str, Any]:
    """Generate Kong gateway configuration"""
    gateway = APIGatewayConfig()

    kong_config = {
        "kong": {
            "database": "postgres",
            "pg_host": "database-service",
            "pg_port": 5432,
            "pg_user": "kong",
            "pg_password": "${KONG_PG_PASSWORD}",
            "pg_database": "kong",
            "admin_listen": "0.0.0.0:8001",
            "proxy_listen": "0.0.0.0:8000",
        },
        "services": gateway.service_mesh.list_services(),
        "routes": gateway.routes,
        "plugins": gateway.plugins,
    }

    return kong_config


def create_traefik_config() -> Dict[str, Any]:
    """Generate Traefik gateway configuration"""
    gateway = APIGatewayConfig()

    traefik_config = {
        "api": {"insecure": False, "address": ":8081"},
        "entrypoints": {
            "web": {"address": ":80"},
            "websecure": {"address": ":443"},
        },
        "providers": {"kubernetes": {"ingressClass": "traefik"}},
        "routers": {},
        "middlewares": {},
        "services": {},
    }

    # Build routers from gateway routes
    for path, config in gateway.routes.items():
        router_name = path.replace("/", "_").lstrip("_")
        traefik_config["routers"][router_name] = {
            "rule": f"PathPrefix(`{path}`)",
            "service": config["upstream"],
            "entrypoints": ["websecure"],
            "middlewares": ["auth", "rate-limit"],
        }

    return traefik_config

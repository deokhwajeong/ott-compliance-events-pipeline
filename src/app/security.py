"""Security utilities for input validation and data sanitization"""

import logging
import re
import html
from typing import Any, Dict, List
import json

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Comprehensive security validation"""
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"('|(--)|;|(\*)|xp_|sp_)",  # SQL keywords
        r"(union|select|insert|update|delete|drop|create|alter)",
        r"(exec|execute|script|javascript|onerror|onclick)"
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"onerror=",
        r"onclick=",
        r"onload=",
        r"<iframe",
        r"<embed",
        r"<object"
    ]
    
    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.",
        r"%2e%2e",
        r"\.\.\\",
    ]
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            return ""
        
        # Limit length
        value = value[:max_length]
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # HTML escape
        value = html.escape(value)
        
        return value.strip()
    
    @staticmethod
    def validate_against_patterns(value: str, patterns: List[str], case_sensitive: bool = False) -> bool:
        """Check if value matches any dangerous patterns"""
        flags = 0 if case_sensitive else re.IGNORECASE
        
        for pattern in patterns:
            if re.search(pattern, value, flags):
                return True
        return False
    
    @staticmethod
    def is_sql_injection_attempt(value: str) -> bool:
        """Detect potential SQL injection"""
        return SecurityValidator.validate_against_patterns(
            value,
            SecurityValidator.SQL_INJECTION_PATTERNS
        )
    
    @staticmethod
    def is_xss_attempt(value: str) -> bool:
        """Detect potential XSS attack"""
        return SecurityValidator.validate_against_patterns(
            value,
            SecurityValidator.XSS_PATTERNS
        )
    
    @staticmethod
    def is_path_traversal_attempt(value: str) -> bool:
        """Detect potential path traversal"""
        return SecurityValidator.validate_against_patterns(
            value,
            SecurityValidator.PATH_TRAVERSAL_PATTERNS
        )
    
    @staticmethod
    def validate_event_data(event: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Comprehensive event data validation.
        Returns: (is_valid, list_of_errors)
        """
        errors = []
        
        # Check for SQL injection in string fields
        string_fields = ['user_id', 'device_id', 'event_id', 'content_id', 'region', 'ip_address']
        for field in string_fields:
            value = event.get(field, "")
            if isinstance(value, str):
                if SecurityValidator.is_sql_injection_attempt(value):
                    errors.append(f"SQL injection detected in {field}")
                    logger.warning(f"Potential SQL injection in {field}: {value[:50]}")
                
                if SecurityValidator.is_xss_attempt(value):
                    errors.append(f"XSS attempt detected in {field}")
                    logger.warning(f"Potential XSS in {field}: {value[:50]}")
        
        # Validate IP address format more strictly
        ip_address = event.get("ip_address", "")
        if ip_address and not SecurityValidator.is_valid_ip(ip_address):
            errors.append(f"Invalid IP address format: {ip_address}")
        
        # Validate timestamp
        timestamp = event.get("timestamp", "")
        if timestamp and not SecurityValidator.is_valid_iso_timestamp(timestamp):
            errors.append(f"Invalid timestamp format: {timestamp}")
        
        # Check extra_metadata for malicious content
        metadata = event.get("extra_metadata", {})
        if isinstance(metadata, dict):
            try:
                # Check if it can be safely serialized
                json.dumps(metadata)
            except:
                errors.append("Invalid extra_metadata: not JSON serializable")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """Validate IP address format (IPv4 or IPv6)"""
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        ipv6_pattern = r'^([0-9a-fA-F]{0,4}:)+[0-9a-fA-F]{0,4}$'
        
        if re.match(ipv4_pattern, ip):
            # Validate octets
            octets = ip.split('.')
            return all(0 <= int(octet) <= 255 for octet in octets)
        
        return re.match(ipv6_pattern, ip) is not None
    
    @staticmethod
    def is_valid_iso_timestamp(timestamp: str) -> bool:
        """Validate ISO format timestamp"""
        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'
        return bool(re.match(iso_pattern, timestamp))


class RateLimiter:
    """Simple rate limiter for API endpoints"""
    
    def __init__(self, max_requests: int = 1000, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed"""
        import time
        
        current_time = time.time()
        
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove old requests outside the window
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if current_time - req_time < self.window_seconds
        ]
        
        # Check if we're under the limit
        if len(self.requests[key]) < self.max_requests:
            self.requests[key].append(current_time)
            return True
        
        return False


class DataSanitizer:
    """Sanitize data before storage"""
    
    @staticmethod
    def sanitize_event(event: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize event data"""
        sanitized = {}
        
        # Sanitize string fields
        string_fields = [
            'user_id', 'device_id', 'event_id', 'content_id',
            'event_type', 'region', 'ip_address', 'error_code'
        ]
        
        for field in string_fields:
            if field in event:
                value = event[field]
                if isinstance(value, str):
                    sanitized[field] = SecurityValidator.sanitize_string(value)
                else:
                    sanitized[field] = value
            else:
                sanitized[field] = ""
        
        # Copy boolean fields
        for field in ['is_eu', 'has_consent']:
            sanitized[field] = event.get(field, False)
        
        # Copy and validate timestamp
        timestamp = event.get('timestamp', '')
        if SecurityValidator.is_valid_iso_timestamp(timestamp):
            sanitized['timestamp'] = timestamp
        else:
            sanitized['timestamp'] = ""
        
        # Copy safe metadata
        if 'extra_metadata' in event:
            try:
                metadata = event['extra_metadata']
                if isinstance(metadata, dict):
                    # Recursively sanitize metadata
                    sanitized['extra_metadata'] = {
                        k: SecurityValidator.sanitize_string(str(v))
                        if isinstance(v, str) else v
                        for k, v in metadata.items()
                    }
                else:
                    sanitized['extra_metadata'] = {}
            except:
                sanitized['extra_metadata'] = {}
        
        sanitized['subscription_plan'] = event.get('subscription_plan', '')
        
        return sanitized


# Global rate limiter
rate_limiter = RateLimiter(max_requests=10000, window_seconds=60)


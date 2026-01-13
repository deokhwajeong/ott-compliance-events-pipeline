"""Audit Log System"""

import logging
import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Audit log actions"""
    LOGIN = "login"
    LOGOUT = "logout"
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    DATA_DELETE = "data_delete"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    COMPLIANCE_CHECK = "compliance_check"
    ANOMALY_DETECTION = "anomaly_detection"
    VIOLATION_RECORDED = "violation_recorded"
    REPORT_GENERATED = "report_generated"
    CONFIG_CHANGE = "config_change"


class ActorRole(str, Enum):
    """Actor roles"""
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"
    AUDITOR = "auditor"


@dataclass
class AuditLog:
    """Audit log entry"""
    timestamp: str
    action: str
    actor_id: str
    actor_role: str
    target_user_id: Optional[str] = None
    target_resource: Optional[str] = None
    details: Optional[dict] = None
    status: str = "success"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self):
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


class AuditLogger:
    """Audit logging system"""
    
    def __init__(self):
        self.logger = logging.getLogger("audit")
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup audit logger"""
        # JSON format logger
        handler = logging.FileHandler('/tmp/audit_logs.jsonl')
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log(
        self,
        action: AuditAction,
        actor_id: str,
        actor_role: ActorRole = ActorRole.SYSTEM,
        target_user_id: Optional[str] = None,
        target_resource: Optional[str] = None,
        details: Optional[dict] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Record audit log"""
        
        audit_log = AuditLog(
            timestamp=datetime.utcnow().isoformat(),
            action=action.value,
            actor_id=actor_id,
            actor_role=actor_role.value,
            target_user_id=target_user_id,
            target_resource=target_resource,
            details=details or {},
            status=status,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Record JSON log
        self.logger.info(audit_log.to_json())
        
        # Also publish to Kafka
        try:
            from .kafka_manager import kafka_manager
            from .kafka_config import kafka_settings
            import asyncio
            
            async def _send():
                await kafka_manager.send_event(
                    topic=kafka_settings.topics["audit_logs"],
                    event=audit_log.to_dict()
                )
            
            # Run if event loop exists, skip otherwise
            try:
                asyncio.run(_send())
            except RuntimeError:
                # Skip if event loop doesn't exist
                pass
        except Exception as e:
            logger.warning(f"Audit log Kafka publish failed: {e}")
        
        return audit_log
    
    def log_data_access(
        self,
        actor_id: str,
        target_user_id: str,
        resource: str,
        actor_role: ActorRole = ActorRole.ADMIN,
        ip_address: Optional[str] = None
    ):
        """Data access log"""
        return self.log(
            action=AuditAction.DATA_ACCESS,
            actor_id=actor_id,
            actor_role=actor_role,
            target_user_id=target_user_id,
            target_resource=resource,
            details={"resource_type": resource},
            ip_address=ip_address
        )
    
    def log_data_export(
        self,
        actor_id: str,
        target_user_id: str,
        export_format: str,
        actor_role: ActorRole = ActorRole.ADMIN,
        ip_address: Optional[str] = None
    ):
        """Data export log"""
        return self.log(
            action=AuditAction.DATA_EXPORT,
            actor_id=actor_id,
            actor_role=actor_role,
            target_user_id=target_user_id,
            target_resource="user_data",
            details={"export_format": export_format},
            ip_address=ip_address
        )
    
    def log_data_delete(
        self,
        actor_id: str,
        target_user_id: str,
        reason: str,
        actor_role: ActorRole = ActorRole.ADMIN,
        ip_address: Optional[str] = None
    ):
        """Data delete log"""
        return self.log(
            action=AuditAction.DATA_DELETE,
            actor_id=actor_id,
            actor_role=actor_role,
            target_user_id=target_user_id,
            target_resource="user_data",
            details={"reason": reason},
            ip_address=ip_address
        )
    
    def log_compliance_check(
        self,
        actor_id: str,
        regulation: str,
        result: str,
        details: Optional[dict] = None
    ):
        """Compliance check log"""
        return self.log(
            action=AuditAction.COMPLIANCE_CHECK,
            actor_id=actor_id,
            target_resource=regulation,
            details={
                "regulation": regulation,
                "result": result,
                **(details or {})
            }
        )
    
    def log_violation(
        self,
        actor_id: str,
        violation_type: str,
        severity: str,
        regulation: str
    ):
        """Violation log"""
        return self.log(
            action=AuditAction.VIOLATION_RECORDED,
            actor_id=actor_id,
            target_resource=regulation,
            details={
                "violation_type": violation_type,
                "severity": severity,
                "regulation": regulation
            },
            status="violation"
        )


# Global audit logger instance
audit_logger = AuditLogger()

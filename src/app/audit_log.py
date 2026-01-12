"""감시 로그 시스템"""

import logging
import json
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """감시 로그 액션"""
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
    """행위자 역할"""
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"
    AUDITOR = "auditor"


@dataclass
class AuditLog:
    """감시 로그 항목"""
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
        """딕셔너리로 변환"""
        return asdict(self)
    
    def to_json(self):
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict())


class AuditLogger:
    """감시 로그 시스템"""
    
    def __init__(self):
        self.logger = logging.getLogger("audit")
        self._setup_logger()
    
    def _setup_logger(self):
        """감시 로거 설정"""
        # JSON 포맷 로거
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
        """감시 로그 기록"""
        
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
        
        # JSON 로그 기록
        self.logger.info(audit_log.to_json())
        
        # Kafka로도 발행
        try:
            from .kafka_manager import kafka_manager
            from .kafka_config import kafka_settings
            import asyncio
            
            async def _send():
                await kafka_manager.send_event(
                    topic=kafka_settings.topics["audit_logs"],
                    event=audit_log.to_dict()
                )
            
            # 이벤트 루프가 있으면 실행, 없으면 스킵
            try:
                asyncio.run(_send())
            except RuntimeError:
                # 이벤트 루프가 없을 경우 스킵
                pass
        except Exception as e:
            logger.warning(f"감시 로그 Kafka 발행 실패: {e}")
        
        return audit_log
    
    def log_data_access(
        self,
        actor_id: str,
        target_user_id: str,
        resource: str,
        actor_role: ActorRole = ActorRole.ADMIN,
        ip_address: Optional[str] = None
    ):
        """데이터 접근 로그"""
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
        """데이터 내보내기 로그"""
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
        """데이터 삭제 로그"""
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
        """규정 준수 검사 로그"""
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
        """규정 위반 로그"""
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


# 전역 감시 로거 인스턴스
audit_logger = AuditLogger()

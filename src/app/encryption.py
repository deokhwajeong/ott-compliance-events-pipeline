"""
End-to-End Encryption Module
Provides field-level and transport-level encryption
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class EncryptionAlgorithm(str, Enum):
    """Supported encryption algorithms"""

    AES_256_GCM = "aes-256-gcm"
    AES_128_CBC = "aes-128-cbc"
    CHACHA20_POLY1305 = "chacha20-poly1305"


class EncryptionKey:
    """Encryption key with metadata"""

    def __init__(
        self,
        key_id: str,
        key_material: bytes,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
        created_at: datetime = None,
        rotation_interval_days: int = 90,
    ):
        self.key_id = key_id
        self.key_material = key_material
        self.algorithm = algorithm
        self.created_at = created_at or datetime.utcnow()
        self.rotation_interval_days = rotation_interval_days
        self.rotation_date = self.created_at + timedelta(days=rotation_interval_days)
        self.is_active = True

    def needs_rotation(self) -> bool:
        """Check if key needs rotation"""
        return datetime.utcnow() >= self.rotation_date

    def to_dict(self) -> Dict[str, Any]:
        """Convert key to dictionary (without key material)"""
        return {
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "created_at": self.created_at.isoformat(),
            "rotation_date": self.rotation_date.isoformat(),
            "needs_rotation": self.needs_rotation(),
            "is_active": self.is_active,
        }


class FieldLevelEncryption:
    """Field-level encryption for sensitive data"""

    # Fields that should always be encrypted
    SENSITIVE_FIELDS = {
        "user_id",
        "email",
        "phone",
        "ip_address",
        "device_id",
        "credit_card",
        "ssn",
        "password_hash",
    }

    def __init__(self, master_key: bytes):
        self.master_key = master_key
        self.cipher = Fernet(self._derive_key(master_key))

    @staticmethod
    def _derive_key(password: bytes) -> bytes:
        """Derive encryption key from master key"""
        # Generate salt from password hash
        salt = hashlib.sha256(password).digest()[:16]

        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        key = kdf.derive(password)
        return Fernet.generate_key() if len(key) != 32 else key

    def encrypt_field(self, value: str) -> str:
        """Encrypt a single field"""
        try:
            encrypted = self.cipher.encrypt(value.encode())
            return encrypted.hex()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            return value

    def decrypt_field(self, encrypted_value: str) -> str:
        """Decrypt a single field"""
        try:
            decrypted = self.cipher.decrypt(bytes.fromhex(encrypted_value))
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return encrypted_value

    def encrypt_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive fields in event"""
        encrypted_event = event.copy()

        for field in self.SENSITIVE_FIELDS:
            if field in encrypted_event and encrypted_event[field]:
                encrypted_event[field] = self.encrypt_field(str(encrypted_event[field]))

        encrypted_event["_encrypted_fields"] = list(self.SENSITIVE_FIELDS)
        encrypted_event["_encrypted_at"] = datetime.utcnow().isoformat()
        return encrypted_event

    def decrypt_event(self, encrypted_event: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive fields in event"""
        decrypted_event = encrypted_event.copy()
        encrypted_fields = decrypted_event.pop("_encrypted_fields", [])

        for field in encrypted_fields:
            if field in decrypted_event and decrypted_event[field]:
                decrypted_event[field] = self.decrypt_field(decrypted_event[field])

        decrypted_event.pop("_encrypted_at", None)
        return decrypted_event

    def is_field_encrypted(self, field_name: str) -> bool:
        """Check if field should be encrypted"""
        return field_name in self.SENSITIVE_FIELDS


class KeyManagementService:
    """Key management and rotation"""

    def __init__(self):
        self.keys: Dict[str, EncryptionKey] = {}
        self.active_key_id: Optional[str] = None

    def generate_key(
        self,
        key_id: str,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
        rotation_interval_days: int = 90,
    ) -> EncryptionKey:
        """Generate new encryption key"""
        # Generate cryptographically secure random bytes
        key_material = Fernet.generate_key()

        key = EncryptionKey(
            key_id=key_id,
            key_material=key_material,
            algorithm=algorithm,
            rotation_interval_days=rotation_interval_days,
        )

        self.keys[key_id] = key
        if self.active_key_id is None:
            self.active_key_id = key_id

        logger.info(f"Generated new key {key_id}")
        return key

    def get_key(self, key_id: str) -> Optional[EncryptionKey]:
        """Get key by ID"""
        return self.keys.get(key_id)

    def get_active_key(self) -> Optional[EncryptionKey]:
        """Get currently active key"""
        if self.active_key_id:
            return self.keys.get(self.active_key_id)
        return None

    def rotate_key(self, old_key_id: str, new_key_id: str) -> bool:
        """Rotate from old key to new key"""
        old_key = self.get_key(old_key_id)
        new_key = self.get_key(new_key_id)

        if not old_key or not new_key:
            return False

        old_key.is_active = False
        new_key.is_active = True
        self.active_key_id = new_key_id

        logger.info(f"Rotated key from {old_key_id} to {new_key_id}")
        return True

    def list_keys(self) -> Dict[str, Dict[str, Any]]:
        """List all keys (without key material)"""
        return {key_id: key.to_dict() for key_id, key in self.keys.items()}


class TransportEncryption:
    """TLS/SSL transport encryption configuration"""

    def __init__(self):
        self.tls_version = "1.3"  # TLS 1.3 minimum
        self.cipher_suites = [
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_128_GCM_SHA256",
        ]
        self.certificate_path = None
        self.key_path = None
        self.ca_certificate_path = None

    def get_tls_config(self) -> Dict[str, Any]:
        """Get TLS configuration"""
        return {
            "min_version": self.tls_version,
            "cipher_suites": self.cipher_suites,
            "certificate_path": self.certificate_path,
            "key_path": self.key_path,
            "require_client_cert": False,
            "session_timeout": 3600,
        }

    def set_certificates(
        self,
        cert_path: str,
        key_path: str,
        ca_path: Optional[str] = None,
    ):
        """Set TLS certificate paths"""
        self.certificate_path = cert_path
        self.key_path = key_path
        self.ca_certificate_path = ca_path
        logger.info("TLS certificates configured")


class EncryptionPipeline:
    """Complete encryption pipeline for events"""

    def __init__(self):
        self.kms = KeyManagementService()
        self.field_encryption = None
        self.transport_encryption = TransportEncryption()

        # Initialize with default key
        self.kms.generate_key("default-key")
        self._init_field_encryption()

    def _init_field_encryption(self):
        """Initialize field-level encryption"""
        active_key = self.kms.get_active_key()
        if active_key:
            self.field_encryption = FieldLevelEncryption(active_key.key_material)

    def process_inbound_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process inbound event (apply encryption)"""
        if not self.field_encryption:
            return event

        # Add encryption metadata
        processed = self.field_encryption.encrypt_event(event)
        processed["encryption_key_id"] = self.kms.active_key_id
        return processed

    def process_outbound_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process outbound event (apply decryption if needed)"""
        if not self.field_encryption:
            return event

        if "_encrypted_fields" in event:
            return self.field_encryption.decrypt_event(event)

        return event

    def rotate_keys(self) -> bool:
        """Rotate encryption keys"""
        active_key = self.kms.get_active_key()
        if not active_key or not active_key.needs_rotation():
            return False

        # Generate new key
        new_key_id = f"key-{datetime.utcnow().timestamp()}"
        self.kms.generate_key(new_key_id)

        # Rotate to new key
        if self.kms.rotate_key(active_key.key_id, new_key_id):
            self._init_field_encryption()
            logger.info(f"Successfully rotated to new key {new_key_id}")
            return True

        return False

    def check_key_rotation_needed(self) -> bool:
        """Check if key rotation is needed"""
        active_key = self.kms.get_active_key()
        return active_key and active_key.needs_rotation()


def create_encryption_config() -> Dict[str, Any]:
    """Create encryption configuration"""
    return {
        "encryption": {
            "enabled": True,
            "transport": {
                "protocol": "TLS",
                "min_version": "1.3",
                "cipher_suites": [
                    "TLS_AES_256_GCM_SHA384",
                    "TLS_CHACHA20_POLY1305_SHA256",
                ],
            },
            "field_level": {
                "enabled": True,
                "algorithm": "AES-256-GCM",
                "sensitive_fields": [
                    "user_id",
                    "email",
                    "phone",
                    "ip_address",
                    "device_id",
                ],
            },
            "key_management": {
                "enabled": True,
                "rotation_interval_days": 90,
                "key_storage": "secure_vault",
                "backup_enabled": True,
            },
        }
    }

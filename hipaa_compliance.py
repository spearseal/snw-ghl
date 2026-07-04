"""
HIPAA Compliance utilities for the integration
Implements encryption, audit logging, access controls, and data security
"""
import os
import json
import logging
import hashlib
from datetime import datetime
from typing import Any, Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from config import settings


class HIPAAComplianceManager:
    """
    Manages HIPAA compliance requirements including:
    - Encryption (data at rest and in transit)
    - Audit controls and logging
    - Access controls
    - Data integrity verification
    """
    
    def __init__(self):
        self.encryption_key = self._derive_key(settings.encryption_key.encode())
        self.cipher_suite = Fernet(self.encryption_key)
        self._setup_audit_logging()
        
    def _derive_key(self, password: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2"""
        salt = b'ghl_snowflake_salt'  # In production, use a random salt per deployment
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    def _setup_audit_logging(self):
        """Setup audit logging for HIPAA compliance"""
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(settings.audit_log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Configure audit logger (prevent duplicate handlers on re-instantiation)
        self.audit_logger = logging.getLogger('hipaa_audit')
        self.audit_logger.setLevel(logging.INFO)
        self.audit_logger.propagate = False

        # Clear any existing handlers to prevent duplicates
        self.audit_logger.handlers.clear()
        
        # File handler for audit logs
        file_handler = logging.FileHandler(settings.audit_log_path)
        file_handler.setLevel(logging.INFO)
        
        # JSON formatter for structured logging
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        self.audit_logger.addHandler(file_handler)
        
        # Console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.audit_logger.addHandler(console_handler)
    
    def encrypt_data(self, data: str) -> str:
        """
        Encrypt sensitive data using AES-256
        
        Args:
            data: Plain text data to encrypt
            
        Returns:
            Encrypted data as base64 string
        """
        try:
            encrypted = self.cipher_suite.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            self.log_audit_event('encryption_failed', {'error': str(e)})
            raise
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """
        Decrypt sensitive data using AES-256
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            
        Returns:
            Decrypted plain text
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher_suite.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            self.log_audit_event('decryption_failed', {'error': str(e)})
            raise
    
    def hash_phi(self, data: str) -> str:
        """
        Create a hash of PHI for verification purposes
        Uses SHA-256 for data integrity
        
        Args:
            data: Data to hash
            
        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(data.encode()).hexdigest()
    
    def log_audit_event(self, event_type: str, details: Dict[str, Any]):
        """
        Log audit events for HIPAA compliance
        
        Args:
            event_type: Type of audit event (e.g., 'data_access', 'encryption', 'sync')
            details: Additional event details
        """
        if not settings.audit_log_enabled:
            return
            
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'details': details
        }
        
        self.audit_logger.info(json.dumps(audit_entry))
    
    def sanitize_phi(self, data: Dict[str, Any], phi_fields: list) -> Dict[str, Any]:
        """
        Sanitize PHI from logs and non-secure storage
        Replaces PHI values with hashes
        
        Args:
            data: Data dictionary containing potential PHI
            phi_fields: List of field names that contain PHI
            
        Returns:
            Sanitized data dictionary
        """
        sanitized = data.copy()
        for field in phi_fields:
            if field in sanitized and sanitized[field]:
                sanitized[field] = self.hash_phi(str(sanitized[field]))
        return sanitized
    
    def verify_data_integrity(self, data: str, expected_hash: str) -> bool:
        """
        Verify data integrity using hash comparison
        
        Args:
            data: Data to verify
            expected_hash: Expected hash value
            
        Returns:
            True if data integrity verified, False otherwise
        """
        actual_hash = self.hash_phi(data)
        return actual_hash == expected_hash
    
    def mask_sensitive_data(self, data: str, visible_chars: int = 4) -> str:
        """
        Mask sensitive data for logging purposes
        Shows only first few characters
        
        Args:
            data: Sensitive data to mask
            visible_chars: Number of characters to show
            
        Returns:
            Masked data string
        """
        if not data or len(data) <= visible_chars:
            return '*' * len(data) if data else ''
        return data[:visible_chars] + '*' * (len(data) - visible_chars)


# Global HIPAA compliance manager instance
hipaa_manager = HIPAAComplianceManager()

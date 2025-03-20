"""Security features for CacheManager.

This module provides functionality for encrypting cached data, signing data
to prevent tampering, and access control mechanisms.
"""

import os
import base64
import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional, Callable, Set
from functools import wraps

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .exceptions import CacheError

logger = logging.getLogger(__name__)

class SecurityError(CacheError):
    """Base exception for security-related errors."""
    pass

class EncryptionError(SecurityError):
    """Exception raised when there's an error with encryption/decryption."""
    pass

class AuthenticationError(SecurityError):
    """Exception raised when there's an error with authentication."""
    pass

class SignatureError(SecurityError):
    """Exception raised when there's an error with data signatures."""
    pass

class CacheEncryptor:
    """Handles encryption and decryption of cache data.
    
    Uses Fernet symmetric encryption for secure storage of sensitive cache data.
    """
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        salt: Optional[str] = None,
        iterations: int = 100000,
        enabled: bool = False
    ):
        """Initialize the encryptor.
        
        Args:
            secret_key: Secret key for encryption (if None, generates a random key)
            salt: Salt for key derivation (if None, generates a random salt)
            iterations: Number of iterations for key derivation
            enabled: Whether encryption is enabled
        
        Raises:
            EncryptionError: If initialization fails
        """
        self.enabled = enabled
        
        if not enabled:
            self._fernet = None
            return
            
        try:
            # Generate or use provided secret key
            if not secret_key:
                # Generate a random key for this session
                secret_key = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')
                logger.warning(
                    "Using randomly generated encryption key. This will not persist "
                    "across restarts. Set a fixed key for persistent encryption."
                )
            
            # Generate or use provided salt
            if not salt:
                salt = os.urandom(16)
            elif isinstance(salt, str):
                salt = salt.encode('utf-8')
                
            # Derive a secure key using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=iterations,
            )
            
            # Derive the key from the secret
            key_bytes = secret_key.encode('utf-8')
            key = base64.urlsafe_b64encode(kdf.derive(key_bytes))
            
            # Create the Fernet instance for encryption/decryption
            self._fernet = Fernet(key)
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {e}")
            raise EncryptionError(f"Failed to initialize encryption: {e}") from e
    
    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data.
        
        Args:
            data: Data to encrypt
            
        Returns:
            bytes: Encrypted data
            
        Raises:
            EncryptionError: If encryption fails
        """
        if not self.enabled or self._fernet is None:
            return data
            
        try:
            return self._fernet.encrypt(data)
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Encryption failed: {e}") from e
    
    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data.
        
        Args:
            data: Encrypted data
            
        Returns:
            bytes: Decrypted data
            
        Raises:
            EncryptionError: If decryption fails
        """
        if not self.enabled or self._fernet is None:
            return data
            
        try:
            return self._fernet.decrypt(data)
        except InvalidToken as e:
            logger.error("Invalid token: data may be corrupted or tampered with")
            raise EncryptionError("Invalid token: data may be corrupted or tampered with") from e
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise EncryptionError(f"Decryption failed: {e}") from e


class DataSigner:
    """Provides functionality to sign and verify cache data.
    
    This helps detect tampering with cached data, even if it's not encrypted.
    """
    
    def __init__(
        self,
        secret_key: str,
        algorithm: str = 'sha256',
        enabled: bool = False
    ):
        """Initialize the data signer.
        
        Args:
            secret_key: Secret key for signing
            algorithm: Hash algorithm to use
            enabled: Whether signing is enabled
            
        Raises:
            SignatureError: If initialization fails
        """
        self.enabled = enabled
        self._algorithm = algorithm
        
        if not enabled:
            return
            
        try:
            # Validate the algorithm
            if algorithm not in hashlib.algorithms_guaranteed:
                raise SignatureError(f"Unsupported hash algorithm: {algorithm}")
                
            self._secret_key = secret_key.encode('utf-8')
        except Exception as e:
            logger.error(f"Failed to initialize data signer: {e}")
            raise SignatureError(f"Failed to initialize data signer: {e}") from e
    
    def sign(self, data: bytes) -> bytes:
        """Sign data to detect tampering.
        
        Args:
            data: Data to sign
            
        Returns:
            bytes: Data with signature appended
            
        Raises:
            SignatureError: If signing fails
        """
        if not self.enabled:
            return data
            
        try:
            # Create HMAC signature
            signature = hmac.new(
                self._secret_key,
                data,
                digestmod=getattr(hashlib, self._algorithm)
            ).digest()
            
            # Append signature to data
            signed_data = data + b'|' + signature
            return signed_data
        except Exception as e:
            logger.error(f"Data signing failed: {e}")
            raise SignatureError(f"Data signing failed: {e}") from e
    
    def verify(self, signed_data: bytes) -> bytes:
        """Verify and extract data from signed data.
        
        Args:
            signed_data: Data with signature
            
        Returns:
            bytes: Original data without signature
            
        Raises:
            SignatureError: If signature verification fails
        """
        if not self.enabled:
            return signed_data
            
        try:
            # Extract data and signature
            data, signature = signed_data.split(b'|', 1)
            
            # Compute expected signature
            expected_signature = hmac.new(
                self._secret_key,
                data,
                digestmod=getattr(hashlib, self._algorithm)
            ).digest()
            
            # Verify signature
            if not hmac.compare_digest(signature, expected_signature):
                raise SignatureError("Signature verification failed: data may be tampered with")
                
            return data
        except ValueError:
            # Wasn't signed data
            logger.warning("Data doesn't contain a signature delimiter")
            return signed_data
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            raise SignatureError(f"Signature verification failed: {e}") from e


class AccessControl:
    """Access control system for cache operations.
    
    Provides role-based access control for cache operations.
    """
    def __init__(self, enabled: bool = False):
        """Initialize access control system.
        
        Args:
            enabled: Whether access control is enabled
        """
        self.enabled = enabled
        self._access_policies = {}
        self._permission_checks = []
        
        # Add default policy if enabled
        if enabled:
            # Default policy allows read for all keys
            self.add_policy('*', allow_read=True, allow_write=False, allow_delete=False)
        
    def add_policy(self, key_pattern: str, 
                   allow_read: bool = True, 
                   allow_write: bool = False, 
                   allow_delete: bool = False,
                   required_roles: Optional[Set[str]] = None):
        """Add an access policy for keys matching a pattern.
        
        Args:
            key_pattern: Pattern to match keys against (supports simple glob patterns)
            allow_read: Whether reading is allowed
            allow_write: Whether writing is allowed
            allow_delete: Whether deletion is allowed
            required_roles: Set of roles required to access matching keys
        """
        self._access_policies[key_pattern] = {
            'read': allow_read,
            'write': allow_write,
            'delete': allow_delete,
            'required_roles': required_roles or set()
        }
        
    def add_permission_check(self, check_func: Callable[[str, str], bool]):
        """Add a custom permission check function.
        
        Args:
            check_func: Function that takes (operation, key) and returns True if allowed
        """
        self._permission_checks.append(check_func)
    
    def set_audit_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set a callback function for audit logging.
        
        Args:
            callback: Function to call with audit information
        """
        self._audit_callback = callback
    
    def check_access(
        self,
        user: Optional[Dict[str, Any]],
        key: str,
        operation: str
    ) -> bool:
        """Check if an operation is allowed on a key.
        
        Args:
            user: Optional user information including roles
            key: Cache key
            operation: Operation type ('read', 'write', 'delete')
            
        Returns:
            bool: True if access is allowed, False otherwise
            
        Raises:
            AuthenticationError: If access is denied
        """
        if not self.enabled:
            return True
            
        # Record for audit logging
        audit_info = {
            'timestamp': time.time(),
            'key': key,
            'operation': operation,
            'user': user or {},
            'access_granted': False
        }
        
        try:
            # Find matching policies
            matching_policies = []
            for pattern, policy in self._access_policies.items():
                # Simple glob matching (could be enhanced with regex)
                if self._match_pattern(pattern, key):
                    matching_policies.append(policy)
                    
            # If no policies match, default to deny
            if not matching_policies:
                raise AuthenticationError(f"No access policy matches key: {key}")
                
            # Check policies
            for policy in matching_policies:
                # Check operation permission
                operation_type = operation
                match operation_type:
                    case "read":
                        if not policy.get('read', False):
                            continue
                    case "write":
                        if not policy.get('write', False):
                            continue
                    case "delete":
                        if not policy.get('delete', False):
                            continue
                    case _:
                        # Unknown operation, default to deny
                        continue
                    
                # Check roles if required
                required_roles = policy['required_roles']
                if required_roles and (not user or not self._has_roles(user, required_roles)):
                    continue
                    
                # Passed all checks for this policy
                audit_info['access_granted'] = True
                
                # Run audit callback if configured
                if hasattr(self, '_audit_callback') and self._audit_callback:
                    self._audit_callback(audit_info)
                    
                # Check custom permission functions
                for check_func in self._permission_checks:
                    if not check_func(operation, key):
                        raise AuthenticationError(f"Custom check denied access to {key}")
                
                return True
                
            # No matching policy granted access
            raise AuthenticationError(
                f"Access denied: {operation} operation not allowed on {key}"
            )
            
        except AuthenticationError as e:
            # Record denial in audit log
            if hasattr(self, '_audit_callback') and self._audit_callback:
                audit_info['error'] = str(e)
                self._audit_callback(audit_info)
                
            raise
    
    def _match_pattern(self, pattern: str, key: str) -> bool:
        """Match a key against a pattern.
        
        Args:
            pattern: Pattern to match against
            key: Cache key to check
            
        Returns:
            bool: True if the key matches the pattern, False otherwise
        """
        # Handle wildcard patterns
        if pattern == '*':
            return True
            
        # Handle prefix wildcards
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return key.startswith(prefix)
            
        # Handle suffix wildcards
        if pattern.startswith('*'):
            suffix = pattern[1:]
            return key.endswith(suffix)
            
        # Exact match
        return pattern == key
        
    def _has_roles(self, user: Dict[str, Any], required_roles: Set[str]) -> bool:
        """Check if a user has the required roles.
        
        Args:
            user: User information dictionary
            required_roles: Set of roles required for access
            
        Returns:
            bool: True if the user has all required roles, False otherwise
        """
        if not required_roles:
            return True
            
        if 'roles' not in user:
            return False
            
        user_roles = set(user['roles'])
        return required_roles.issubset(user_roles)


def require_permission(operation: str) -> Callable:
    """Decorator to enforce access control for cache operations.
    
    Args:
        operation: The operation being performed (e.g., "read", "write")
        
    Returns:
        Callable: Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Skip if access control is not enabled
            if not hasattr(self, '_access_control') or not self._access_control.enabled:
                return await func(self, *args, **kwargs)
            
            # Get the key from arguments (first argument for most cache operations)
            key = args[0] if args else kwargs.get('key')
            
            if key is None:
                logger.warning("No key provided to access control check")
                return await func(self, *args, **kwargs)
            
            # Get user context if available
            user = getattr(self, '_current_user', None)
            
            # Check access
            self._access_control.check_access(user, key, operation)
            
            # If access is allowed, proceed with the function
            return await func(self, *args, **kwargs)
        
        return wrapper
    return decorator 
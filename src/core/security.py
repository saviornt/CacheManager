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
from typing import Any, Dict, Optional, Callable, Union, Tuple
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
    """Provides access control for cache operations.
    
    Controls which operations are allowed on which cache keys based on
    configurable policies.
    """
    
    def __init__(self, enabled: bool = False):
        """Initialize access control.
        
        Args:
            enabled: Whether access control is enabled
        """
        self.enabled = enabled
        self._access_policies: Dict[str, Dict[str, Any]] = {}
        self._audit_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    
    def add_policy(
        self,
        pattern: str,
        allow_read: bool = True,
        allow_write: bool = True,
        allow_delete: bool = True,
        required_roles: Optional[set] = None
    ) -> None:
        """Add an access policy for a key pattern.
        
        Args:
            pattern: Glob pattern to match cache keys
            allow_read: Whether reading is allowed
            allow_write: Whether writing is allowed
            allow_delete: Whether deletion is allowed
            required_roles: Set of roles required for access
        """
        if not self.enabled:
            return
            
        self._access_policies[pattern] = {
            'allow_read': allow_read,
            'allow_write': allow_write,
            'allow_delete': allow_delete,
            'required_roles': required_roles or set()
        }
    
    def set_audit_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set a callback function for audit logging.
        
        Args:
            callback: Function to call with audit information
        """
        self._audit_callback = callback
    
    def check_access(
        self,
        key: str,
        operation: str,
        user: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if an operation is allowed on a key.
        
        Args:
            key: Cache key
            operation: Operation type ('read', 'write', 'delete')
            user: Optional user information including roles
            
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
            
            # Check each matching policy
            for policy in matching_policies:
                # Check operation permission
                if operation == 'read' and not policy['allow_read']:
                    continue
                elif operation == 'write' and not policy['allow_write']:
                    continue
                elif operation == 'delete' and not policy['allow_delete']:
                    continue
                
                # Check roles if required
                required_roles = policy['required_roles']
                if required_roles:
                    if not user or 'roles' not in user:
                        continue
                    
                    user_roles = set(user['roles'])
                    if not required_roles.issubset(user_roles):
                        continue
                
                # If we get here, access is granted
                audit_info['access_granted'] = True
                
                # Call audit callback if set
                if self._audit_callback:
                    self._audit_callback(audit_info)
                
                return True
            
            # If no policy grants access, deny
            raise AuthenticationError(
                f"Access denied for operation {operation} on key: {key}"
            )
            
        except AuthenticationError:
            # Call audit callback if set
            if self._audit_callback:
                self._audit_callback(audit_info)
            raise
        except Exception as e:
            # Log unexpected errors
            logger.error(f"Error in access control: {e}")
            
            # Call audit callback if set
            if self._audit_callback:
                audit_info['error'] = str(e)
                self._audit_callback(audit_info)
            
            # Default to deny on errors
            raise AuthenticationError(f"Access control error: {e}") from e
    
    def _match_pattern(self, pattern: str, key: str) -> bool:
        """Match a key against a pattern.
        
        Currently implements simple glob matching with * as wildcard.
        
        Args:
            pattern: Glob pattern
            key: Cache key
            
        Returns:
            bool: True if pattern matches key
        """
        if pattern == '*':
            return True
            
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return key.startswith(prefix)
            
        if pattern.startswith('*'):
            suffix = pattern[1:]
            return key.endswith(suffix)
            
        if '*' in pattern:
            parts = pattern.split('*')
            if key.startswith(parts[0]) and key.endswith(parts[-1]):
                return True
                
        return pattern == key


def require_permission(operation: str):
    """Decorator to enforce access control on cache operations.
    
    Args:
        operation: Type of operation ('read', 'write', 'delete')
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
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
            self._access_control.check_access(key, operation, user)
            
            # If access is allowed, proceed with the function
            return await func(self, *args, **kwargs)
        
        return wrapper
    return decorator 
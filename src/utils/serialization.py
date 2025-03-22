"""Serialization utilities for CacheManager."""

import pickle
import zlib
import logging
import msgpack
from typing import Any, Optional, Dict

from ..core.exceptions import CacheSerializationError

logger = logging.getLogger(__name__)

class Serializer:
    """Handles data serialization and deserialization for cache values.
    
    This class provides methods to serialize and deserialize values with msgpack,
    with optional compression, encryption, and signing.
    """
    
    def __init__(self, 
                 enable_compression: bool = False,
                 compression_min_size: int = 1024,
                 compression_level: int = 6,
                 encryptor = None,
                 data_signer = None,
                 stats: Optional[Dict[str, int]] = None,
                 correlation_id: str = None):
        """Initialize the serializer.
        
        Args:
            enable_compression: Whether to enable compression
            compression_min_size: Minimum size for compression to be applied
            compression_level: Zlib compression level (0-9)
            encryptor: Optional encryptor instance for encryption
            data_signer: Optional data signer instance for signing
            stats: Optional dictionary for tracking error statistics
            correlation_id: Correlation ID for logging
        """
        self.enable_compression = enable_compression
        self.compression_min_size = compression_min_size
        self.compression_level = compression_level
        self.encryptor = encryptor
        self.data_signer = data_signer
        self.stats = stats
        self.correlation_id = correlation_id

    def serialize(self, value: Any) -> bytes:
        """Serialize a value for storage.
        
        Serializes the value with msgpack (or pickle if msgpack not available),
        and optionally compresses, encrypts, and signs it.
        
        Args:
            value: The value to serialize
            
        Returns:
            bytes: The serialized value
            
        Raises:
            CacheSerializationError: If serialization fails
        """
        try:
            # Serialize with msgpack
            serialized = msgpack.packb(value, use_bin_type=True)
            
            # Compress if enabled and the value is large enough
            if (self.enable_compression and 
                len(serialized) >= self.compression_min_size):
                compressed = zlib.compress(serialized, level=self.compression_level)
                serialized = b'C' + compressed  # Prefix with 'C' to indicate compression
            else:
                serialized = b'U' + serialized  # Prefix with 'U' to indicate uncompressed
            
            # Encrypt if enabled
            if self.encryptor and self.encryptor.enabled:
                serialized = self.encryptor.encrypt(serialized)
            
            # Sign if enabled
            if self.data_signer and self.data_signer.enabled:
                serialized = self.data_signer.sign(serialized)
            
            return serialized
        except Exception as e:
            logger.error(
                f"Failed to serialize value: {e}", 
                extra={"correlation_id": self.correlation_id}
            )
            if self.stats:
                self.stats["errors"] = self.stats.get("errors", 0) + 1
            raise CacheSerializationError(f"Failed to serialize value: {e}") from e

    def deserialize(self, data: bytes) -> Any:
        """Deserialize a value from storage.
        
        Deserializes a value previously serialized with serialize.
        
        Args:
            data: The data to deserialize
            
        Returns:
            The deserialized value
            
        Raises:
            CacheSerializationError: If deserialization fails
        """
        try:
            # Verify signature if enabled
            if self.data_signer and self.data_signer.enabled:
                data = self.data_signer.verify(data)
            
            # Decrypt if enabled
            if self.encryptor and self.encryptor.enabled:
                data = self.encryptor.decrypt(data)
            
            # Check for compression flag
            if data.startswith(b'C'):  # Compressed
                decompressed = zlib.decompress(data[1:])
                return msgpack.unpackb(decompressed, raw=False, ext_hook=self._decode_complex_types)
            elif data.startswith(b'U'):  # Uncompressed
                return msgpack.unpackb(data[1:], raw=False, ext_hook=self._decode_complex_types)
            else:
                # Legacy data without compression flag
                return msgpack.unpackb(data, raw=False, ext_hook=self._decode_complex_types)
        except Exception as e:
            logger.error(
                f"Failed to deserialize data: {e}", 
                extra={"correlation_id": self.correlation_id}
            )
            if self.stats:
                self.stats["errors"] = self.stats.get("errors", 0) + 1
            raise CacheSerializationError(f"Failed to deserialize data: {e}") from e

    def _decode_complex_types(self, code: str, data: Any) -> Any:
        """Decode complex types like datetimes from serialized form.
        
        Args:
            code: Type code from serialization
            data: Serialized data
            
        Returns:
            Any: Deserialized data with proper Python types
        """
        # Currently we don't have custom types, but this allows for future extension
        return data

def serialize(value: Any, enable_compression: bool = False, 
             compression_min_size: int = 1024,
             compression_level: int = 6) -> bytes:
    """Serialize a value using msgpack if available, otherwise pickle.
    
    Args:
        value: The value to serialize
        enable_compression: Whether to enable compression for large values
        compression_min_size: Minimum size in bytes for compression to be applied
        compression_level: Compression level (1-9) for zlib
        
    Returns:
        bytes: The serialized value
        
    Raises:
        CacheSerializationError: If serialization fails
    """
    try:
        data = msgpack.packb(value, use_bin_type=True)
        
        # Apply compression if enabled and the data size meets the minimum
        if enable_compression and len(data) >= compression_min_size:
            compressed = zlib.compress(data, level=compression_level)
            # Prepend a simple marker to identify compressed data
            return b'C' + compressed
        
        # If not compressed, use a different marker
        return b'U' + data
    except Exception as e:
        raise CacheSerializationError(f"Failed to serialize data: {e}")

def deserialize(data: bytes) -> Any:
    """Deserialize a value using msgpack if available, otherwise pickle.
    
    Args:
        data: The serialized data
        
    Returns:
        Any: The deserialized value
        
    Raises:
        CacheSerializationError: If deserialization fails
    """
    if not data:
        return None
    
    try:
        # Check the marker to determine if data is compressed
        marker, payload = data[0:1], data[1:]
        
        # Decompress if necessary
        if marker == b'C':
            payload = zlib.decompress(payload)
        elif marker != b'U':
            # For backward compatibility - if no marker, assume uncompressed
            payload = data
        
        return msgpack.unpackb(payload, raw=False)
    except Exception as e:
        raise CacheSerializationError(f"Failed to deserialize data: {e}") 
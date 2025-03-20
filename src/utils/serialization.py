"""Serialization utilities for CacheManager."""

import pickle
import zlib
import logging
from typing import Any

from ..core.exceptions import CacheSerializationError

logger = logging.getLogger(__name__)

# Try to import msgpack for more efficient serialization
try:
    import msgpack
    HAS_MSGPACK = True
except ImportError:
    msgpack = None
    HAS_MSGPACK = False
    logger.warning("msgpack not installed, falling back to pickle for serialization", 
                  extra={'correlation_id': 'INIT'})

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
        if HAS_MSGPACK:
            data = msgpack.packb(value, use_bin_type=True)
        else:
            data = pickle.dumps(value)
        
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
        
        if HAS_MSGPACK:
            return msgpack.unpackb(payload, raw=False)
        else:
            return pickle.loads(payload)
    except Exception as e:
        raise CacheSerializationError(f"Failed to deserialize data: {e}") 
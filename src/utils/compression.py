"""Utility functions for data compression and decompression."""

import zlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

def compress_data(value: Any, config: Any) -> Any:
    """Compress data if it's large enough.
    
    Args:
        value: The data to potentially compress
        config: Configuration object with compression settings
        
    Returns:
        Any: Compressed data or original data if compression isn't applicable
    """
    if not config.enable_compression:
        return value
        
    # Only compress string or bytes data
    if not isinstance(value, (str, bytes)):
        return value
        
    # Convert string to bytes if needed
    data = value.encode('utf-8') if isinstance(value, str) else value
    
    # Only compress data larger than the minimum size
    if len(data) < config.compression_min_size:
        return value
        
    # Compress the data
    try:
        compressed = zlib.compress(data, level=config.compression_level)
        logger.debug(
            f"Compressed data from {len(data)} to {len(compressed)} bytes "
            f"({len(compressed)/len(data):.2%})"
        )
        
        # Return compressed bytes, or decoded string if input was string
        if isinstance(value, str):
            # Add a prefix to indicate this is compressed data that was originally a string
            return f"__COMPRESSED_STR__{compressed.hex()}"
        else:
            # Add a prefix to indicate this is compressed data that was originally bytes
            return b"__COMPRESSED_BYTES__" + compressed
    except Exception as e:
        logger.error(f"Compression error: {e}")
        return value

def decompress_data(value: Any, config: Any) -> Any:
    """Decompress data that was previously compressed.
    
    Args:
        value: The potentially compressed data
        config: Configuration object with compression settings
        
    Returns:
        Any: Decompressed data or original data if not compressed
    """
    if not config.enable_compression:
        return value
        
    # Check for compressed string data
    if isinstance(value, str) and value.startswith('__COMPRESSED_STR__'):
        try:
            # Extract the compressed data (remove prefix)
            compressed_hex = value[len('__COMPRESSED_STR__'):]
            compressed = bytes.fromhex(compressed_hex)
            
            # Decompress and decode back to string
            decompressed = zlib.decompress(compressed)
            return decompressed.decode('utf-8')
        except Exception as e:
            logger.error(f"String decompression error: {e}")
            return value
            
    # Check for compressed bytes data
    elif isinstance(value, bytes) and value.startswith(b'__COMPRESSED_BYTES__'):
        try:
            # Extract the compressed data (remove prefix)
            compressed = value[len(b'__COMPRESSED_BYTES__'):]
            
            # Decompress
            return zlib.decompress(compressed)
        except Exception as e:
            logger.error(f"Bytes decompression error: {e}")
            return value
            
    # Return original value if not compressed
    return value 
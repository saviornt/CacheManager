"""Tests for compression functionality in CacheManager."""

import os
import asyncio
import logging
import pytest

from src.cache_manager import CacheManager
from src.cache_config import CacheConfig, CacheLayerType, CacheLayerConfig

# Configure logger
logger = logging.getLogger(__name__)

@pytest.fixture
def compression_config(tmp_path):
    """Fixture providing cache config for testing compression features."""
    cache_dir = tmp_path / "cache_compression"
    os.makedirs(cache_dir, exist_ok=True)
    
    return CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="compression.db",
        cache_max_size=50,
        cache_ttl=300.0,
        use_redis=False,
        retry_attempts=1,
        retry_delay=1,
        memory_cache_enabled=True,
        use_layered_cache=True,
        enable_compression=True,
        compression_min_size=50,  # Compress values larger than 50 bytes
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=20),
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )

@pytest.mark.asyncio
async def test_cache_compression(compression_config):
    """Test cache compression feature."""
    print("\nTesting cache compression...")
    
    cm = CacheManager(config=compression_config)
    
    # Create a large value that exceeds compression_min_size
    large_value = "x" * 1000
    
    # Also test with a small value that shouldn't be compressed
    small_value = "small"
    
    # Set both values
    await cm.set("large_key", large_value)
    await cm.set("small_key", small_value)
    print("  ✓ Set large and small values in cache")
    
    # Retrieve and verify both values
    retrieved_large = await cm.get("large_key")
    retrieved_small = await cm.get("small_key")
    
    assert retrieved_large == large_value, "Large value should be correctly retrieved after compression"
    assert retrieved_small == small_value, "Small value should be correctly retrieved without compression"
    print("  ✓ Retrieved compressed and uncompressed values correctly")
    
    # Verify compression was used by direct inspection of serialize method
    # Create a test value larger than the threshold
    test_value = "x" * 200  # Well above our 50 byte threshold
    
    # Call _serialize directly and check if it has the compression marker
    serialized = cm._serialize(test_value)
    assert serialized[0:1] == b'C', "Large value should be compressed (should start with 'C' marker)"
    
    # Small value should not be compressed
    small_test = "tiny"
    serialized_small = cm._serialize(small_test)
    assert serialized_small[0:1] == b'U', "Small value should not be compressed (should start with 'U' marker)"
    
    print("  ✓ Verified compression is active for large values and inactive for small values")
    
    # Clean up
    await cm.clear()
    await cm.close()
    print("  ✓ Compression test completed!")

@pytest.mark.asyncio
async def test_compression_with_different_thresholds(tmp_path):
    """Test compression with different thresholds."""
    print("\nTesting compression with different thresholds...")
    
    # Cache directory
    cache_dir = tmp_path / "cache_compression_thresholds"
    os.makedirs(cache_dir, exist_ok=True)
    
    # Test with various compression thresholds
    thresholds = [10, 100, 500]
    
    for threshold in thresholds:
        # Configure with different threshold
        config = CacheConfig(
            cache_dir=str(cache_dir),
            cache_file=f"compression_{threshold}.db",
            enable_compression=True,
            compression_min_size=threshold
        )
        
        cm = CacheManager(config=config)
        
        try:
            # Values of different sizes
            tiny_value = "x" * 5
            small_value = "x" * 50
            medium_value = "x" * 200
            large_value = "x" * 1000
            
            # Set all values
            await cm.set("tiny", tiny_value)
            await cm.set("small", small_value)
            await cm.set("medium", medium_value)
            await cm.set("large", large_value)
            
            # Check what gets compressed with current threshold
            serialized_tiny = cm._serialize(tiny_value)
            serialized_small = cm._serialize(small_value)
            serialized_medium = cm._serialize(medium_value)
            serialized_large = cm._serialize(large_value)
            
            # Check compression status (U = uncompressed, C = compressed)
            print(f"  Threshold {threshold} bytes:")
            print(f"    - Tiny value (5 bytes): {'compressed' if serialized_tiny[0:1] == b'C' else 'uncompressed'}")
            print(f"    - Small value (50 bytes): {'compressed' if serialized_small[0:1] == b'C' else 'uncompressed'}")
            print(f"    - Medium value (200 bytes): {'compressed' if serialized_medium[0:1] == b'C' else 'uncompressed'}")
            print(f"    - Large value (1000 bytes): {'compressed' if serialized_large[0:1] == b'C' else 'uncompressed'}")
            
            # Verify values are correctly retrieved
            assert await cm.get("tiny") == tiny_value
            assert await cm.get("small") == small_value
            assert await cm.get("medium") == medium_value
            assert await cm.get("large") == large_value
            
            # Correct check based on threshold
            if threshold <= 5:
                assert serialized_tiny[0:1] == b'C', "Tiny value should be compressed"
            else:
                assert serialized_tiny[0:1] == b'U', "Tiny value should not be compressed"
                
            if threshold <= 50:
                assert serialized_small[0:1] == b'C', "Small value should be compressed"
            else:
                assert serialized_small[0:1] == b'U', "Small value should not be compressed"
                
            if threshold <= 200:
                assert serialized_medium[0:1] == b'C', "Medium value should be compressed"
            else:
                assert serialized_medium[0:1] == b'U', "Medium value should not be compressed"
                
            # Large value should always be compressed with these thresholds
            assert serialized_large[0:1] == b'C', "Large value should be compressed"
            
        finally:
            await cm.clear()
            await cm.close()
    
    print("  ✓ Compression with different thresholds test completed!")

if __name__ == "__main__":
    """Run compression tests directly."""
    asyncio.run(test_cache_compression(None))
    # Can't easily run test_compression_with_different_thresholds directly due to tmp_path fixture 
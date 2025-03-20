"""Tests for enhanced caching features like bulk operations and circuit breakers."""

import os
import asyncio
import logging
import pytest

from src.cache_manager import CacheManager
from src.cache_config import CacheConfig, CacheLayerType, CacheLayerConfig
from src.core.exceptions import CacheError

# Configure logger
logger = logging.getLogger(__name__)

@pytest.fixture
def enhanced_config(tmp_path):
    """Fixture providing cache config for testing enhanced features."""
    cache_dir = tmp_path / "cache_enhanced"
    os.makedirs(cache_dir, exist_ok=True)
    
    return CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="enhanced.db",
        cache_max_size=50,
        cache_ttl=300.0,
        use_redis=False,
        retry_attempts=1,
        retry_delay=1,
        memory_cache_enabled=True,
        use_layered_cache=True,
        enable_compression=True,
        compression_min_size=50,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=20),
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )

@pytest.mark.asyncio
async def test_get_many_set_many(enhanced_config):
    """Test bulk get_many and set_many operations."""
    print("\nTesting bulk operations...")
    cm = CacheManager(config=enhanced_config)
    
    # Create test data
    test_data = {
        "bulk_key1": "value1",
        "bulk_key2": {"nested": "value2"},
        "bulk_key3": ["list", "of", "values"],
        "bulk_key4": 12345,
        "bulk_key5": True
    }
    
    # Test set_many
    await cm.set_many(test_data)
    print("  ✓ Set multiple values with set_many")
    
    # Test get_many with all keys
    result_all = await cm.get_many(list(test_data.keys()))
    assert len(result_all) == len(test_data), "Should return all requested keys"
    for key, value in test_data.items():
        assert result_all[key] == value, f"Value for {key} doesn't match"
    print("  ✓ Retrieved all values with get_many")
    
    # Test get_many with subset of keys
    subset_keys = ["bulk_key1", "bulk_key3", "nonexistent_key"]
    result_subset = await cm.get_many(subset_keys)
    assert len(result_subset) == 2, "Should return only existing keys"
    assert result_subset["bulk_key1"] == test_data["bulk_key1"]
    assert result_subset["bulk_key3"] == test_data["bulk_key3"]
    assert "nonexistent_key" not in result_subset
    print("  ✓ Retrieved subset of values with get_many, ignoring nonexistent keys")
    
    # Clean up
    await cm.clear()
    await cm.close()
    print("  ✓ Bulk operations test completed!")

@pytest.mark.asyncio
async def test_cache_compression(enhanced_config):
    """Test cache compression feature."""
    print("\nTesting cache compression...")
    enhanced_config.enable_compression = True
    enhanced_config.compression_min_size = 50
    
    cm = CacheManager(config=enhanced_config)
    
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
async def test_circuit_breaker(enhanced_config):
    """Test circuit breaker pattern."""
    print("\nTesting circuit breaker pattern...")
    cm = CacheManager(config=enhanced_config)
    disk_layer = cm._cache_layers[CacheLayerType.DISK]
    
    # Create a key in the disk layer
    key = "circuit_test"
    namespaced_key = cm._namespace_key(key)
    await disk_layer.set(namespaced_key, "original_value")
    
    # Get success state of circuit breakers before testing
    get_breaker = disk_layer._shelve_get_breaker
    success_before = get_breaker.allow_request()
    assert success_before, "Circuit should be closed initially"
    print("  ✓ Circuit breaker initially closed (allowing requests)")
    
    # Force some failing operations by mocking the shelve operations
    error_message = "Simulated disk failure"
    
    # Define a function that raises an exception directly
    def failing_sync_get(*args, **kwargs):
        raise Exception(error_message)
    
    # Target the _shelve_get function in the disk layer
    original_sync_get = disk_layer._sync_get
    try:
        # Replace with failing operation
        disk_layer._sync_get = failing_sync_get
        
        # Attempt operations that will fail
        for _ in range(disk_layer._shelve_get_breaker.failure_threshold + 1):
            try:
                await disk_layer.get(namespaced_key)
            except Exception as e:
                logger.error(f"Error in circuit breaker test: {e}")
                pass
        
        # Now the circuit should be open
        success_after = get_breaker.allow_request()
        assert not success_after, "Circuit should be open after failures"
        print("  ✓ Circuit breaker opened after multiple failures")
        
        # Wait for circuit to close again
        print(f"  Waiting for circuit to reset (timeout: {get_breaker.reset_timeout}s)...")
        await asyncio.sleep(get_breaker.reset_timeout + 1)
        
        # Circuit should be half-open now
        success_after_timeout = get_breaker.allow_request()
        assert success_after_timeout, "Circuit should be half-open after timeout"
        print("  ✓ Circuit breaker switched to half-open state after timeout")
        
    finally:
        # Restore original implementation
        disk_layer._sync_get = original_sync_get
    
    # Verify we can get the value again after restoring
    has_value, restored_value = await disk_layer.get(namespaced_key)
    assert has_value and restored_value == "original_value", "Should get original value after restoring implementation"
    print("  ✓ Cache operations restored after test")
    
    # Clean up
    await cm.clear()
    await cm.close()
    print("  ✓ Circuit breaker test completed!")

@pytest.mark.asyncio
async def test_retry_mechanism(enhanced_config):
    """Test retry mechanism for failed operations."""
    print("\nTesting retry mechanism...")
    # Configure fewer retries for faster testing
    enhanced_config.retry_attempts = 2
    enhanced_config.retry_delay = 1
    
    cm = CacheManager(config=enhanced_config)
    
    # Mock the get method of the disk layer to fail initially and then succeed
    disk_layer = cm._cache_layers[CacheLayerType.DISK]
    original_get = disk_layer.get
    
    failure_count = 0
    
    async def mock_get(key):
        nonlocal failure_count
        if failure_count < 1:  # Fail once, then succeed
            failure_count += 1
            raise CacheError("Simulated read failure")
        else:
            return True, "retry_value"
    
    # Apply mock
    disk_layer.get = mock_get
    
    try:        
        # First clear memory layer to ensure we hit disk layer
        memory_layer = cm._cache_layers[CacheLayerType.MEMORY]
        await memory_layer.clear()
        
        # Get value, which should retry until success
        value = await cm.get("retry_key")
        
        # Should have retried and eventually succeeded
        assert value == "retry_value", "Should get value after retry succeeds"
        assert failure_count == 1, "Should have retried once"
        print(f"  ✓ Retry succeeded after {failure_count} failures")
        
    finally:
        # Restore original function
        disk_layer.get = original_get
    
    # Clean up
    await cm.clear()
    await cm.close()
    print("  ✓ Retry mechanism test completed!")

@pytest.mark.asyncio
async def test_cached_decorator(enhanced_config):
    """Test the @cached decorator for function results."""
    print("\nTesting @cached decorator...")
    cm = CacheManager(config=enhanced_config)
    
    call_count = 0
    
    @cm.cached(ttl=30)
    async def expensive_operation(arg1, arg2):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # Simulate work
        return f"Result: {arg1 + arg2}"
    
    # First call should execute the function
    result1 = await expensive_operation(40, 2)
    assert result1 == "Result: 42"
    assert call_count == 1
    print("  ✓ First call executes function")
    
    # Second call with same args should use cache
    result2 = await expensive_operation(40, 2)
    assert result2 == "Result: 42"
    assert call_count == 1  # Still 1, didn't call function again
    print("  ✓ Second call uses cached result")
    
    # Call with different args should execute function again
    result3 = await expensive_operation(50, 10)
    assert result3 == "Result: 60"
    assert call_count == 2  # Increased, called function again
    print("  ✓ Call with different arguments executes function")
    
    # Clean up
    await cm.clear()
    await cm.close()
    print("  ✓ Cached decorator test completed!") 
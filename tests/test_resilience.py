"""Tests for resilience features in CacheManager (circuit breaker and retry mechanism)."""

import os
import asyncio
import logging
import pytest
import pytest_asyncio

from src.cache_manager import CacheManager
from src.cache_config import CacheConfig, CacheLayerType, CacheLayerConfig
from src.core.exceptions import CacheError

# Configure logger
logger = logging.getLogger(__name__)

@pytest_asyncio.fixture(scope="function")
async def resilience_config(tmp_path):
    """Fixture providing cache config for testing resilience features."""
    cache_dir = tmp_path / "cache_resilience"
    os.makedirs(cache_dir, exist_ok=True)
    
    config = CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="resilience.db",
        cache_max_size=50,
        cache_ttl=300.0,
        use_redis=False,
        retry_attempts=3,
        retry_delay=1,
        memory_cache_enabled=True,
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=20),
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )
    
    yield config
    
    # Cleanup code after test completes
    # No specific cleanup needed for the config object itself

@pytest.mark.asyncio
async def test_circuit_breaker(resilience_config):
    """Test circuit breaker pattern."""
    print("\nTesting circuit breaker pattern...")
    cm = CacheManager(config=resilience_config)
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
async def test_retry_mechanism(resilience_config):
    """Test retry mechanism for failed operations."""
    print("\nTesting retry mechanism...")
    # Configure fewer retries for faster testing
    resilience_config.retry_attempts = 2
    resilience_config.retry_delay = 1
    
    cm = CacheManager(config=resilience_config)
    
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
async def test_retry_mechanism_exceeding_attempts(resilience_config):
    """Test retry mechanism when we exceed maximum retry attempts."""
    print("\nTesting retry mechanism with too many failures...")
    # Configure for limited retries
    resilience_config.retry_attempts = 2
    resilience_config.retry_delay = 0.5  # Short delay for faster tests
    
    cm = CacheManager(config=resilience_config)
    
    # Mock the get method of the disk layer to always fail
    disk_layer = cm._cache_layers[CacheLayerType.DISK]
    original_get = disk_layer.get
    
    attempt_count = 0
    
    async def mock_get_always_fails(key):
        nonlocal attempt_count
        attempt_count += 1
        raise CacheError(f"Simulated failure #{attempt_count}")
    
    # Apply mock
    disk_layer.get = mock_get_always_fails
    
    try:        
        # First clear memory layer to ensure we hit disk layer
        memory_layer = cm._cache_layers[CacheLayerType.MEMORY]
        await memory_layer.clear()
        
        # Attempt to get value, which should fail after retries
        try:
            await cm.get("retry_fail_key")
            # If we get here, the test has failed
            assert False, "Should have raised an exception after exceeding retry attempts"
        except Exception as e:
            # This is expected - check if it's a RetryError or contains a CacheError
            from tenacity import RetryError
            assert isinstance(e, RetryError) or isinstance(e, CacheError), f"Expected RetryError or CacheError, got {type(e)}"
            # Check we retried the right number of times
            expected_attempts = resilience_config.retry_attempts + 1  # Initial attempt + retries
            assert attempt_count == expected_attempts, f"Should have attempted {expected_attempts} times, but attempted {attempt_count} times"
            print(f"  ✓ Failed after {attempt_count} attempts, as expected")
        
    finally:
        # Restore original function
        disk_layer.get = original_get
    
    # Clean up
    await cm.clear()
    await cm.close()
    print("  ✓ Retry mechanism failure test completed!")

if __name__ == "__main__":
    """Run resilience tests directly."""
    asyncio.run(test_circuit_breaker(None))
    asyncio.run(test_retry_mechanism(None)) 
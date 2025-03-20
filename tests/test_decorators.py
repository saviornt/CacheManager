"""Tests for CacheManager decorators (@cached)."""

import os
import asyncio
import logging
import pytest

from src.cache_manager import CacheManager
from src.cache_config import CacheConfig, CacheLayerType, CacheLayerConfig

# Configure logger
logger = logging.getLogger(__name__)

@pytest.fixture
def decorator_config(tmp_path):
    """Fixture providing cache config for testing decorator features."""
    cache_dir = tmp_path / "cache_decorators"
    os.makedirs(cache_dir, exist_ok=True)
    
    return CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="decorators.db",
        cache_max_size=50,
        cache_ttl=300.0,
        use_redis=False,
        retry_attempts=1,
        retry_delay=1,
        memory_cache_enabled=True,
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=20),
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )

@pytest.mark.asyncio
async def test_cached_decorator(decorator_config):
    """Test the @cached decorator for function results."""
    print("\nTesting @cached decorator...")
    cm = CacheManager(config=decorator_config)
    
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

@pytest.mark.asyncio
async def test_cached_decorator_with_custom_key(decorator_config):
    """Test the @cached decorator with custom key function."""
    print("\nTesting @cached decorator with custom key function...")
    cm = CacheManager(config=decorator_config)
    
    call_count = 0
    
    # Key function that ignores the second argument
    def custom_key_func(arg1, arg2):
        return f"custom:{arg1}"
    
    @cm.cached(ttl=30, key_func=custom_key_func)
    async def operation_with_custom_key(arg1, arg2):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # Simulate work
        return f"Custom: {arg1}-{arg2}"
    
    # First call
    result1 = await operation_with_custom_key("abc", 123)
    assert result1 == "Custom: abc-123"
    assert call_count == 1
    print("  ✓ First call executes function")
    
    # Second call with different second arg but same first arg
    # Should still hit cache because of custom key function
    result2 = await operation_with_custom_key("abc", 456)
    assert result2 == "Custom: abc-123"  # Original cached result
    assert call_count == 1  # Still 1, didn't call function again
    print("  ✓ Second call with same first arg hits cache despite different second arg")
    
    # Call with different first arg should execute function again
    result3 = await operation_with_custom_key("def", 123)
    assert result3 == "Custom: def-123"
    assert call_count == 2  # Increased, called function again
    print("  ✓ Call with different first argument executes function")
    
    # Clean up
    await cm.clear()
    await cm.close()
    print("  ✓ Cached decorator with custom key test completed!")

@pytest.mark.asyncio
async def test_cached_decorator_invalidation(decorator_config):
    """Test invalidation of cached function results."""
    print("\nTesting @cached decorator invalidation...")
    cm = CacheManager(config=decorator_config)
    
    call_count = 0
    
    @cm.cached(ttl=30)
    async def cached_function(value):
        nonlocal call_count
        call_count += 1
        return f"Processed: {value}"
    
    # Call the function to populate cache
    result1 = await cached_function("test")
    assert result1 == "Processed: test"
    assert call_count == 1
    
    # Call again to verify caching works
    result2 = await cached_function("test")
    assert result2 == "Processed: test"
    assert call_count == 1  # Still 1, using cached result
    
    # Invalidate the cache for this function and argument
    await cm.invalidate_cached(cached_function, "test")
    
    # Call again, should execute the function
    result3 = await cached_function("test")
    assert result3 == "Processed: test"
    assert call_count == 2  # Increased, called function again after invalidation
    print("  ✓ Function executed again after cache invalidation")
    
    # Clean up
    await cm.clear()
    await cm.close()
    print("  ✓ Cached decorator invalidation test completed!")

if __name__ == "__main__":
    """Run decorator tests directly."""
    asyncio.run(test_cached_decorator(None)) 
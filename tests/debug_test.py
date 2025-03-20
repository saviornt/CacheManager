"""Debug test for diagnosing issues with the cached decorator."""

import asyncio
import logging
import time

from src.cache_manager import CacheManager, logger
from src.cache_config import CacheConfig

# Configure verbose logging
logging.basicConfig(level=logging.DEBUG)
logger.setLevel(logging.DEBUG)

async def main():
    """Test the cached decorator functionality."""
    print("\n\nRunning debug test for cached decorator...")
    
    # Create cache directory
    import os
    os.makedirs(".cache", exist_ok=True)
    
    # Use a simple config with minimal cache size
    cm = CacheManager(CacheConfig(
        cache_max_size=10,
        cache_ttl=300,
        memory_cache_enabled=True,
        memory_cache_ttl=60
    ))
    
    call_count = 0
    
    # Define a function that will be decorated with the cache decorator
    @cm.cached(ttl=60)
    async def example_function(a: int, b: int) -> int:
        """Example function that adds two numbers."""
        nonlocal call_count
        call_count += 1
        print(f">>> FUNCTION CALLED with {a}, {b}")
        # Simulate some work
        time.sleep(0.1)
        return a + b
    
    # First call should execute the function
    print("\n*** First call (2, 3) ***")
    result1 = await example_function(2, 3)
    print(f">>> RESULT: {result1}, Call count: {call_count}")
    
    # Second call with same args should use cache
    print("\n*** Second call (2, 3) - should use cache ***")
    start = time.time()
    result2 = await example_function(2, 3)
    elapsed = time.time() - start
    print(f">>> RESULT: {result2}, Call count: {call_count}")
    print(f">>> TIME ELAPSED: {elapsed:.6f} seconds (should be fast if cached)")
    
    # Manually check if the key exists in the cache
    module_name = example_function.__module__
    func_name = example_function.__name__
    key = f"{module_name}:{func_name}:2:3"
    print(f"\n*** Checking cache for key: {key} ***")
    # Check if it's in memory cache
    namespaced_key = cm._namespace_key(key)
    in_memory = namespaced_key in cm._memory_cache
    print(f">>> In memory cache: {in_memory}")
    if in_memory:
        print(f">>> Memory cache value: {cm._memory_cache.get(namespaced_key)}")
    
    # Call with different args should execute the function again
    print("\n*** Call with different args (3, 4) ***")
    result3 = await example_function(3, 4)
    print(f">>> RESULT: {result3}, Call count: {call_count}")
    
    # Clean up
    await cm.clear()
    await cm.close()
    print("\nTest complete")

if __name__ == "__main__":
    asyncio.run(main()) 
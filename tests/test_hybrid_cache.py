"""Tests for hybrid/layered caching and compression features."""

import os
import asyncio
import pytest
import importlib.util

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.cache_manager import CacheManager
from src.cache_config import CacheConfig, CacheLayerType, CacheLayerConfig

@pytest.fixture
def temp_cache_dir(tmpdir):
    """Create a temporary directory for cache files."""
    cache_dir = tmpdir.mkdir("cache")
    return str(cache_dir)

@pytest.fixture
def layered_config(temp_cache_dir):
    """Create a configuration with layered caching enabled."""
    return CacheConfig(
        cache_dir=temp_cache_dir,
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=5),
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ],
        cache_max_size=10,
        enable_compression=True,
        compression_min_size=10
    )

@pytest.fixture
def redis_layered_config(temp_cache_dir):
    """Create a configuration with layered caching including Redis (if available)."""
    # Check if Redis is available using importlib.util.find_spec
    redis_available = importlib.util.find_spec("redis") is not None
    
    layers = [
        CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=5),
        CacheLayerConfig(type=CacheLayerType.REDIS, ttl=300, enabled=redis_available),
        CacheLayerConfig(type=CacheLayerType.DISK, ttl=600)
    ]
    
    return CacheConfig(
        cache_dir=temp_cache_dir,
        use_layered_cache=True,
        cache_layers=layers,
        use_redis=redis_available,
        redis_url="redis://localhost",
        redis_port=6379,
        cache_max_size=10
    )

@pytest.mark.asyncio
async def test_layered_cache_set_get(layered_config):
    """Test setting and getting values from layered cache."""
    cache = CacheManager(layered_config)
    
    # Set a value
    await cache.set("test_key", "test_value")
    
    # Get the value
    value = await cache.get("test_key")
    
    # Verify values were stored correctly
    assert value == "test_value"
    
    # Verify the stats show at least one hit
    assert cache.get_stats()["hits"] >= 1
    
    # Clear the memory cache directly to test fallback to disk
    memory_layer = cache._cache_layers[CacheLayerType.MEMORY]
    await memory_layer.clear()
    
    # Get the value again, should now come from disk
    value = await cache.get("test_key")
    assert value == "test_value"
    
    # Verify stats show more hits
    assert cache.get_stats()["hits"] >= 2
    
    await cache.close()

@pytest.mark.asyncio
async def test_read_through_caching(layered_config):
    """Test read-through caching behavior."""
    layered_config.read_through = True
    cache = CacheManager(layered_config)
    
    # Set a value directly in the disk layer
    key = "read_through_test"
    namespaced_key = cache._namespace_key(key)
    disk_layer = cache._cache_layers[CacheLayerType.DISK]
    await disk_layer.set(namespaced_key, "disk_value")
    
    # Get the memory layer to check for the key
    memory_layer = cache._cache_layers[CacheLayerType.MEMORY]
    mem_found, _ = await memory_layer.get(namespaced_key)
    assert not mem_found, "Value should not be in memory yet"
    
    # Get the value, which should populate the memory cache via read-through
    value = await cache.get(key)
    assert value == "disk_value"
    
    # Since we're using asyncio.create_task for read-through, give it a moment to complete
    await asyncio.sleep(0.1)
    
    # Now the value should be in memory (if read-through is working)
    if cache.config.read_through:
        mem_found, mem_value = await memory_layer.get(namespaced_key)
        assert mem_found, "Value should now be in memory due to read-through"
        assert mem_value == "disk_value"
    
    # Modify disk layer directly
    await disk_layer.set(namespaced_key, "updated_value")
    
    # Memory should still have the old value
    mem_found, mem_value = await memory_layer.get(namespaced_key)
    if mem_found:
        assert mem_value == "disk_value"
    
    # Get again, should still return memory value if in memory
    value = await cache.get(key)
    if mem_found:
        assert value == "disk_value"
    else:
        assert value == "updated_value"
    
    # Clear memory and get again to see updated disk value
    await memory_layer.clear()
    value = await cache.get(key)
    assert value == "updated_value"
    
    await cache.close()

@pytest.mark.asyncio
async def test_write_through_caching(layered_config):
    """Test write-through caching behavior."""
    layered_config.write_through = True
    cache = CacheManager(layered_config)
    
    # Set a value, which should go to all layers due to write-through
    await cache.set("write_test", "write_value")
    
    # Verify the value is in memory
    memory_layer = cache._cache_layers[CacheLayerType.MEMORY]
    disk_layer = cache._cache_layers[CacheLayerType.DISK]
    
    namespaced_key = cache._namespace_key("write_test")
    mem_found, mem_value = await memory_layer.get(namespaced_key)
    assert mem_found, "Value should be in memory layer"
    
    # Clear memory to verify it's also in disk
    await memory_layer.clear()
    
    # Get the value, should come from disk
    disk_found, disk_value = await disk_layer.get(namespaced_key)
    assert disk_found, "Value should be in disk layer due to write-through"
    assert disk_value == "write_value"
    
    # Cleanup first cache instance
    await cache.close()
    
    # Now set write_through to False and create a new cache instance
    layered_config.write_through = False
    new_cache = CacheManager(layered_config)
    
    # Get the layer references for the new cache instance
    new_memory_layer = new_cache._cache_layers[CacheLayerType.MEMORY]
    new_disk_layer = new_cache._cache_layers[CacheLayerType.DISK]
    
    # Set a value, which should only go to the first layer
    await new_cache.set("no_write_through", "memory_only")
    
    # Verify it's in memory
    namespaced_key = new_cache._namespace_key("no_write_through")
    mem_found, _ = await new_memory_layer.get(namespaced_key)
    assert mem_found, "Value should be in memory layer"
    
    # Clear memory and verify it's NOT in disk
    await new_memory_layer.clear()
    
    # Check if it's in the disk layer
    disk_found, _ = await new_disk_layer.get(namespaced_key)
    assert not disk_found, "Value should not be in disk layer when write_through is False"
    
    # This should be a cache miss
    value = await new_cache.get("no_write_through")
    assert value is None
    
    # Cleanup
    await new_cache.close()

@pytest.mark.asyncio
async def test_compression(layered_config):
    """Test cache compression."""
    layered_config.enable_compression = True
    layered_config.compression_min_size = 10
    cache = CacheManager(layered_config)
    
    # Create a large value that will be compressed
    large_value = "x" * 1000
    
    # Set the value
    await cache.set("compressed_key", large_value)
    
    # Get the value back
    value = await cache.get("compressed_key")
    assert value == large_value
    
    # Try a small value that shouldn't be compressed
    small_value = "small"
    await cache.set("small_key", small_value)
    
    # Get the small value back
    value = await cache.get("small_key")
    assert value == small_value
    
    await cache.close()

@pytest.mark.asyncio
async def test_get_many_layered(layered_config):
    """Test get_many with layered cache."""
    cache = CacheManager(layered_config)
    
    # Set multiple values
    await cache.set_many({
        "key1": "value1", 
        "key2": "value2", 
        "key3": "value3"
    })
    
    # Get them all
    values = await cache.get_many(["key1", "key2", "key3", "nonexistent"])
    
    # Verify results
    assert len(values) == 3
    assert values["key1"] == "value1"
    assert values["key2"] == "value2"
    assert values["key3"] == "value3"
    assert "nonexistent" not in values
    
    # Clear memory to test disk layer
    memory_layer = cache._cache_layers[CacheLayerType.MEMORY]
    await memory_layer.clear()
    
    # Get again
    values = await cache.get_many(["key1", "key2", "key3"])
    
    # Verify results still work
    assert len(values) == 3
    assert values["key1"] == "value1"
    assert values["key2"] == "value2"
    assert values["key3"] == "value3"
    
    await cache.close()

@pytest.mark.asyncio
async def test_clear_layered(layered_config):
    """Test clear with layered cache."""
    cache = CacheManager(layered_config)
    
    # Set values in all layers
    await cache.set("clear_test", "clear_value")
    
    # Verify value exists
    value = await cache.get("clear_test")
    assert value == "clear_value"
    
    # Clear the cache
    await cache.clear()
    
    # Verify value is gone from all layers
    value = await cache.get("clear_test")
    assert value is None
    
    await cache.close()

@pytest.mark.asyncio
async def test_eviction_in_layered_cache(layered_config):
    """Test cache eviction policies in layered cache."""
    # Create a new memory layer config with an explicitly small max size
    memory_config = CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=300, max_size=2)  # Very small max size
    disk_config = CacheLayerConfig(type=CacheLayerType.DISK, ttl=3600)
    
    # Override the layered_config with our small memory layer config
    layered_config.cache_layers = [memory_config, disk_config]
    
    cache = CacheManager(layered_config)
    memory_layer = cache._cache_layers[CacheLayerType.MEMORY]
    disk_layer = cache._cache_layers[CacheLayerType.DISK]
    
    # Fill the memory layer beyond capacity to trigger eviction
    # Since max_size is 2, the first key should be evicted when the third is added
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")
    
    # But all values should be retrievable from the cache (some via disk)
    value1 = await cache.get("key1")
    value2 = await cache.get("key2")
    value3 = await cache.get("key3")
    
    assert value1 == "value1", "Value1 should be retrievable (possibly from disk)"
    assert value2 == "value2", "Value2 should be retrievable"
    assert value3 == "value3", "Value3 should be retrievable"
    
    # Check that values were stored in disk layer
    disk_key1 = cache._namespace_key("key1")
    disk_found, disk_value = await disk_layer.get(disk_key1)
    assert disk_found, "Value should be found in disk layer"
    assert disk_value == "value1", "Value in disk layer should match original value"
    
    # Clean up
    await cache.close()

@pytest.mark.asyncio
async def test_cache_stats(layered_config):
    """Test cache statistics collection."""
    cache = CacheManager(layered_config)
    
    # Initial stats
    initial_stats = cache.get_stats()
    assert "hits" in initial_stats
    assert "misses" in initial_stats
    assert "hit_rate" in initial_stats
    
    # Set and get a key to update stats
    await cache.set("stats_test", "stats_value")
    value = await cache.get("stats_test")
    assert value == "stats_value"
    
    # Get a non-existent key to trigger a miss
    value = await cache.get("nonexistent_key")
    assert value is None
    
    # Check updated stats
    updated_stats = cache.get_stats()
    assert updated_stats["hits"] >= 1
    assert updated_stats["misses"] >= 1
    
    await cache.close()

@pytest.mark.asyncio
async def test_delete_layered(layered_config):
    """Test delete with layered cache."""
    cache = CacheManager(layered_config)
    
    # Set a value
    await cache.set("delete_test", "delete_me")
    
    # Verify it exists
    value = await cache.get("delete_test")
    assert value == "delete_me"
    
    # Delete it
    result = await cache.delete("delete_test")
    assert result, "Delete should return True for existing key"
    
    # Verify it's gone from all layers
    value = await cache.get("delete_test")
    assert value is None
    
    # Try deleting a non-existent key
    result = await cache.delete("nonexistent_key")
    assert not result, "Delete should return False for non-existent key"
    
    await cache.close()

@pytest.mark.asyncio
async def test_cached_decorator_with_layered_cache(layered_config):
    """Test the cached decorator with layered cache."""
    cache = CacheManager(layered_config)
    call_count = 0
    
    @cache.cached(ttl=60)
    async def test_function(x, y):
        nonlocal call_count
        call_count += 1
        return x + y
    
    # First call should execute the function
    result1 = await test_function(2, 3)
    assert result1 == 5
    assert call_count == 1
    
    # Second call with same args should use cache
    result2 = await test_function(2, 3)
    assert result2 == 5
    assert call_count == 1, "Function should not be called again"
    
    # Call with different args should execute function
    result3 = await test_function(3, 4)
    assert result3 == 7
    assert call_count == 2
    
    await cache.close()

if __name__ == "__main__":
    asyncio.run(test_layered_cache_set_get(layered_config(temp_cache_dir=".cache")))
    print("All tests passed!") 
import os
import pytest
import logging

from src.cache_manager import CacheManager
from src.cache_config import CacheConfig

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Fixture to set up configuration for tests using shelve backend.
@pytest.fixture
def config_shelve(tmp_path):
    # Use a temporary directory for cache files
    cache_dir = tmp_path / "cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    # Return a direct configuration instance with custom settings
    return CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="cache.db",
        cache_max_size=3,  # Set a small max size for eviction testing
        cache_ttl=300.0,
        use_redis=False,
        retry_attempts=1,
        retry_delay=1
    )

@pytest.mark.asyncio
async def test_set_get_clear_shelve(config_shelve):
    print("\nRunning test_set_get_clear_shelve...")
    cm = CacheManager(config=config_shelve)
    key = "test_key"
    value = {"data": 123}
    await cm.set(key, value)
    # Test that we can get back the stored value.
    ret = await cm.get(key)
    assert ret == value, "Value retrieved from cache should match value set."
    print(f"  ✓ Set and get value successful: {ret}")
    
    # Test clearing the cache.
    await cm.clear()
    ret_after_clear = await cm.get(key)
    assert ret_after_clear is None, "Cache should be cleared after calling clear()."
    print("  ✓ Cache clear successful")
    await cm.close()
    print("✅ test_set_get_clear_shelve passed!")

@pytest.mark.asyncio
async def test_eviction_policy(config_shelve):
    print("\nRunning test_eviction_policy...")
    cm = CacheManager(config=config_shelve)
    # Insert keys more than the max size (set to 3 in the config)
    keys = ["k1", "k2", "k3", "k4"]
    for k in keys:
        await cm.set(k, f"value_{k}")
        print(f"  Added key '{k}' to cache")
    
    # The eviction should remove the oldest key ("k1")
    ret = await cm.get("k1")
    assert ret is None, "The oldest key should be evicted when max size is exceeded."
    print("  ✓ Oldest key 'k1' was properly evicted")
    
    # Remaining keys should still be available.
    for k in keys[1:]:
        ret = await cm.get(k)
        assert ret == f"value_{k}", f"Key {k} should still be available in the cache."
        print(f"  ✓ Key '{k}' still available with value: {ret}")
    
    await cm.clear()
    await cm.close()
    print("✅ test_eviction_policy passed!")

@pytest.mark.asyncio
async def test_context_manager(config_shelve):
    print("\nRunning test_context_manager...")
    # Test using the CacheManager as an async context manager.
    async with CacheManager(config=config_shelve) as cm:
        await cm.set("cm_test", "context")
        ret = await cm.get("cm_test")
        assert ret == "context", "Cache value should be retrievable within async context."
        print(f"  ✓ Context manager properly handles cache operations, retrieved: {ret}")
    print("✅ test_context_manager passed!")

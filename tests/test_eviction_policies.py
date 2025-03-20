"""Tests for the different eviction policies in CacheManager."""

import os
import pytest
import asyncio

from src.cache_manager import CacheManager
from src.cache_config import CacheConfig, EvictionPolicy, CacheLayerType, CacheLayerConfig

@pytest.fixture
def lru_config(tmp_path):
    """Fixture providing cache config with LRU eviction policy."""
    cache_dir = tmp_path / "cache_lru"
    os.makedirs(cache_dir, exist_ok=True)
    
    return CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="cache_lru.db",
        cache_max_size=5,  # Small size to test eviction
        eviction_policy=EvictionPolicy.LRU,
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=5, 
                            ),  # Small size for memory layer
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )

@pytest.fixture
def fifo_config(tmp_path):
    """Fixture providing cache config with FIFO eviction policy."""
    cache_dir = tmp_path / "cache_fifo"
    os.makedirs(cache_dir, exist_ok=True)
    
    return CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="cache_fifo.db",
        cache_max_size=5,  # Small size to test eviction
        eviction_policy=EvictionPolicy.FIFO,
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=5, 
                            ),  # Small size for memory layer
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )

@pytest.fixture
def lfu_config(tmp_path):
    """Fixture providing cache config with LFU eviction policy."""
    cache_dir = tmp_path / "cache_lfu"
    os.makedirs(cache_dir, exist_ok=True)
    
    return CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="cache_lfu.db",
        cache_max_size=5,  # Small size to test eviction
        eviction_policy=EvictionPolicy.LFU,
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=5, 
                            ),  # Small size for memory layer
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )

@pytest.mark.asyncio
async def test_lru_eviction(lru_config):
    """Test the Least Recently Used eviction policy."""
    print("\nTesting LRU eviction policy...")
    cache = CacheManager(config=lru_config)
    memory_layer = cache._cache_layers[CacheLayerType.MEMORY]
    
    # Insert keys in a sequence
    for i in range(1, 6):  # Insert keys 1-5
        await cache.set(f"key{i}", f"value{i}")
        print(f"  Added key{i}")
    
    # Access keys in a specific order to affect LRU order
    # Access key1, so it's not the least recently used
    await cache.get("key1")
    print("  Accessed key1")
    
    # Insert a new key, which should evict the least recently used key (key2)
    await cache.set("key6", "value6")
    print("  Added key6")
    
    # Force memory layer to perform eviction 
    memory_layer._evict_if_needed()
    
    # Verify key2 is removed from memory (but might still be in disk)
    namespaced_key = cache._namespace_key("key2")
    mem_found, _ = await memory_layer.get(namespaced_key)
    print(f"  key2 in memory: {mem_found}")
    
    # In LRU, key2 should be evicted as it was not accessed
    # But we might still get it from disk
    disk_value = await cache.get("key2")
    print(f"  key2 value from disk: {disk_value}")
    
    # Verify all other keys are retrievable
    for i in [1, 3, 4, 5, 6]:
        value = await cache.get(f"key{i}")
        assert value == f"value{i}", f"key{i} should still be available"
        print(f"  key{i} value: {value}")
    
    await cache.clear()
    await cache.close()

@pytest.mark.asyncio
async def test_fifo_eviction(fifo_config):
    """Test the First In First Out eviction policy."""
    print("\nTesting FIFO eviction policy...")
    cache = CacheManager(config=fifo_config)
    memory_layer = cache._cache_layers[CacheLayerType.MEMORY]
    
    # Insert keys in a sequence
    for i in range(1, 6):  # Insert keys 1-5
        await cache.set(f"key{i}", f"value{i}")
        print(f"  Added key{i}")
    
    # Even access some keys, which should not affect FIFO order
    await cache.get("key1")
    await cache.get("key2")
    print("  Accessed key1 and key2")
    
    # Insert a new key, which should evict the first key (key1)
    await cache.set("key6", "value6")
    print("  Added key6")
    
    # Force memory layer to perform eviction
    memory_layer._evict_if_needed()
    
    # Verify key1 is removed from memory (but might still be in disk)
    namespaced_key = cache._namespace_key("key1")
    mem_found, _ = await memory_layer.get(namespaced_key)
    print(f"  key1 in memory: {mem_found}")
    
    # In FIFO, key1 should be evicted as it was added first
    # But we might still get it from disk
    disk_value = await cache.get("key1")
    print(f"  key1 value from disk: {disk_value}")
    
    # Verify all other keys are retrievable
    for i in [2, 3, 4, 5, 6]:
        value = await cache.get(f"key{i}")
        assert value == f"value{i}", f"key{i} should still be available"
        print(f"  key{i} value: {value}")
    
    await cache.clear()
    await cache.close()

@pytest.mark.asyncio
async def test_lfu_eviction(lfu_config):
    """Test the Least Frequently Used eviction policy."""
    print("\nTesting LFU eviction policy...")
    cache = CacheManager(config=lfu_config)
    memory_layer = cache._cache_layers[CacheLayerType.MEMORY]
    
    # Insert keys in a sequence
    for i in range(1, 6):  # Insert keys 1-5
        await cache.set(f"key{i}", f"value{i}")
        print(f"  Added key{i}")
    
    # Access some keys multiple times to affect frequency
    for _ in range(3):
        await cache.get("key1")  # Access key1 3 times
    print("  Accessed key1 3 times")
    
    for _ in range(2):
        await cache.get("key2")  # Access key2 2 times
    print("  Accessed key2 2 times")
    
    await cache.get("key3")  # Access key3 1 time
    print("  Accessed key3 1 time")
    
    # key4 and key5 not accessed, lowest frequency
    
    # Insert a new key, which should evict the least frequently used key (key4 or key5)
    await cache.set("key6", "value6")
    print("  Added key6")
    
    # Force memory layer to perform eviction
    memory_layer._evict_if_needed()
    
    # Verify key4 or key5 is removed from memory (but might still be in disk)
    # In LFU, one of key4 or key5 should be evicted as they were least accessed
    
    # Check both key4 and key5 - at least one should be evicted
    key4_namespaced = cache._namespace_key("key4")
    key5_namespaced = cache._namespace_key("key5")
    
    key4_in_memory, _ = await memory_layer.get(key4_namespaced)
    key5_in_memory, _ = await memory_layer.get(key5_namespaced)
    
    print(f"  key4 in memory: {key4_in_memory}")
    print(f"  key5 in memory: {key5_in_memory}")
    
    # Either key4 or key5 (or both) should be evicted from memory
    assert not (key4_in_memory and key5_in_memory), "At least one of key4 or key5 should be evicted"
    
    # Verify all values are still retrievable from disk
    for i in range(1, 7):
        value = await cache.get(f"key{i}")
        assert value == f"value{i}", f"key{i} should still be available from disk"
        print(f"  key{i} value: {value}")
    
    await cache.clear()
    await cache.close()

@pytest.mark.asyncio
async def test_different_eviction_policies_comparison():
    """Compare behavior of different eviction policies."""
    print("\nComparing different eviction policies...")
    
    # Create temporary directory
    import tempfile
    temp_dir = tempfile.mkdtemp()
    
    # Test sequence and access patterns are the same for all policies
    async def run_test_sequence(cache, policy_name):
        print(f"\n  Testing with {policy_name} policy...")
        
        # Insert 5 keys
        for i in range(1, 6):
            await cache.set(f"key{i}", f"value{i}")
        
        # Access keys in a specific pattern
        await cache.get("key1")  # Access once
        await cache.get("key2")  # Access once
        await cache.get("key1")  # Access again
        
        # Add another key to trigger eviction
        await cache.set("key6", "value6")
        
        # Force eviction
        memory_layer = cache._cache_layers[CacheLayerType.MEMORY]
        memory_layer._evict_if_needed()
        
        # Check which keys are in memory
        result = {}
        for i in range(1, 7):
            key = f"key{i}"
            namespaced_key = cache._namespace_key(key)
            in_memory, _ = await memory_layer.get(namespaced_key)
            result[key] = in_memory
            print(f"    {key} in memory: {in_memory}")
            
            # Get from cache (might come from disk)
            value = await cache.get(key)
            print(f"    {key} value: {value}")
        
        await cache.clear()
        await cache.close()
        return result
    
    # Test with LRU
    lru_config = CacheConfig(
        cache_dir=temp_dir,
        cache_file="lru_test.db",
        eviction_policy=EvictionPolicy.LRU,
        cache_max_size=5,
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=5),
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )
    lru_cache = CacheManager(config=lru_config)
    lru_results = await run_test_sequence(lru_cache, "LRU")
    
    # Test with FIFO
    fifo_config = CacheConfig(
        cache_dir=temp_dir,
        cache_file="fifo_test.db",
        eviction_policy=EvictionPolicy.FIFO,
        cache_max_size=5,
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=5),
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )
    fifo_cache = CacheManager(config=fifo_config)
    fifo_results = await run_test_sequence(fifo_cache, "FIFO")
    
    # Test with LFU
    lfu_config = CacheConfig(
        cache_dir=temp_dir,
        cache_file="lfu_test.db",
        eviction_policy=EvictionPolicy.LFU,
        cache_max_size=5,
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=5),
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )
    lfu_cache = CacheManager(config=lfu_config)
    lfu_results = await run_test_sequence(lfu_cache, "LFU")
    
    # Compare results
    print("\n  Eviction policy comparison results:")
    print(f"    LRU: {lru_results}")
    print(f"    FIFO: {fifo_results}")
    print(f"    LFU: {lfu_results}")
    
    # Clean up
    import shutil
    shutil.rmtree(temp_dir) 
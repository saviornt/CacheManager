"""Tests for the namespace functionality of CacheManager."""

import os
import pytest
from typing import Dict, Any

from src.cache_manager import CacheManager
from src.cache_config import CacheConfig, CacheLayerType, CacheLayerConfig

@pytest.fixture
def namespace1_config(tmp_path):
    """Fixture providing cache config with namespace1."""
    cache_dir = tmp_path / "cache_ns"
    os.makedirs(cache_dir, exist_ok=True)
    
    return CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="cache.db",
        cache_max_size=100,
        cache_ttl=300.0,
        use_redis=False,
        retry_attempts=1,
        memory_cache_enabled=True,
        namespace="namespace1",
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=50),
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )

@pytest.fixture
def namespace2_config(tmp_path):
    """Fixture providing cache config with namespace2."""
    cache_dir = tmp_path / "cache_ns"
    os.makedirs(cache_dir, exist_ok=True)
    
    return CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="cache.db",
        cache_max_size=100,
        cache_ttl=300.0,
        use_redis=False,
        retry_attempts=1,
        memory_cache_enabled=True,
        namespace="namespace2",
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=50),
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )

@pytest.mark.asyncio
async def test_namespace_isolation(namespace1_config, namespace2_config):
    """Test that different namespaces isolate cache data."""
    # Create two cache managers with different namespaces
    cm1 = CacheManager(config=namespace1_config)
    cm2 = CacheManager(config=namespace2_config)
    
    # Set the same key in both namespaces with different values
    key = "test_key"
    value1 = {"namespace": "namespace1", "data": "value1"}
    value2 = {"namespace": "namespace2", "data": "value2"}
    
    await cm1.set(key, value1)
    await cm2.set(key, value2)
    
    # Verify that each namespace has its own value
    result1 = await cm1.get(key)
    result2 = await cm2.get(key)
    
    assert result1 == value1, "Namespace 1 should retrieve its own value"
    assert result2 == value2, "Namespace 2 should retrieve its own value"
    assert result1 != result2, "Values from different namespaces should be different"
    
    # Clean up
    await cm1.clear()
    await cm2.clear()
    await cm1.close()
    await cm2.close()

@pytest.mark.asyncio
async def test_bulk_operations_with_namespaces(namespace1_config, namespace2_config):
    """Test bulk operations with namespaces."""
    cm1 = CacheManager(config=namespace1_config)
    cm2 = CacheManager(config=namespace2_config)
    
    # Create test data for each namespace
    test_data1: Dict[str, Any] = {
        "key1": "value1_ns1",
        "key2": "value2_ns1",
        "key3": "value3_ns1",
    }
    
    test_data2: Dict[str, Any] = {
        "key1": "value1_ns2",
        "key2": "value2_ns2",
        "key3": "value3_ns2",
    }
    
    # Set data in both namespaces
    await cm1.set_many(test_data1)
    await cm2.set_many(test_data2)
    
    # Get data from each namespace
    results1 = await cm1.get_many(list(test_data1.keys()))
    results2 = await cm2.get_many(list(test_data2.keys()))
    
    # Verify correct values were retrieved
    assert results1 == test_data1, "Namespace 1 should retrieve its own values"
    assert results2 == test_data2, "Namespace 2 should retrieve its own values"
    
    # Try to get namespace2 keys from namespace1 cache
    empty_results = await cm1.get_many(["ns2_only_key"])
    assert empty_results == {}, "Should return empty dict for keys not in namespace"
    
    # Clean up
    await cm1.clear()
    await cm2.clear()
    await cm1.close()
    await cm2.close()

@pytest.mark.asyncio
async def test_namespaced_keys_helpers():
    """Test the namespace key helper methods."""
    # Create cache manager with a namespace
    cm = CacheManager(config=CacheConfig(namespace="test"))
    
    # Test _namespace_key
    assert cm._namespace_key("mykey") == "test:mykey", "Key should be prefixed with namespace"
    
    # Test _remove_namespace
    assert cm._remove_namespace("test:mykey") == "mykey", "Namespace should be removed from key"
    
    # Test with default namespace
    cm_default = CacheManager(config=CacheConfig(namespace="default"))
    assert cm_default._namespace_key("mykey") == "mykey", "Default namespace should not modify key"
    assert cm_default._remove_namespace("mykey") == "mykey", "Default namespace should not affect removal"
    
    # Test dictionary helpers
    test_dict = {"key1": "value1", "key2": "value2"}
    namespaced_dict = cm._namespace_keys_dict(test_dict)
    assert namespaced_dict == {"test:key1": "value1", "test:key2": "value2"}, "All keys should be namespaced"
    
    original_dict = cm._remove_namespace_from_keys_dict(namespaced_dict)
    assert original_dict == test_dict, "Namespace should be removed from all keys"
    
    await cm.close()
    await cm_default.close() 
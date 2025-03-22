"""Tests for bulk operations (get_many, set_many) in CacheManager."""

import os
import asyncio
import logging
import pytest

from src.cache_manager import CacheManager
from src.cache_config import CacheConfig, CacheLayerType, CacheLayerConfig

# Configure logger
logger = logging.getLogger(__name__)

@pytest.fixture
def bulk_ops_config(tmp_path):
    """Fixture providing cache config for testing bulk operations."""
    cache_dir = tmp_path / "cache_bulk_ops"
    os.makedirs(cache_dir, exist_ok=True)
    
    return CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="bulk_ops.db",
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
async def test_get_many_set_many(bulk_ops_config):
    """Test bulk get_many and set_many operations."""
    print("\nTesting bulk operations...")
    cm = CacheManager(config=bulk_ops_config)
    
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

if __name__ == "__main__":
    """Run bulk operations tests directly."""
    asyncio.run(test_get_many_set_many(None)) 
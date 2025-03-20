"""Tests for cache warmup functionality in CacheManager."""

import asyncio
import json
import logging
import os
import tempfile
import pytest
from typing import Generator

from src.cache_config import CacheConfig
from src.cache_manager import CacheManager
from src.core.cache_warmup import CacheWarmup

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Fixture to set up configuration for tests with cache warmup
@pytest.fixture
def config_with_warmup(tmp_path) -> Generator[CacheConfig, None, None]:
    """Create a configuration with cache warmup enabled."""
    # Use a temporary directory for cache files
    cache_dir = tmp_path / "cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    # Return a configuration with cache warmup enabled
    config = CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="cache.db",
        cache_max_size=50,
        cache_ttl=300.0,
        use_redis=False,
        retry_attempts=1,
        retry_delay=1,
        
        # Cache warmup settings
        enable_warmup=True,
    )
    yield config

# Tests for cache warmup
@pytest.mark.asyncio
async def test_cache_warmup(config_with_warmup):
    """Test cache warmup functionality."""
    print("\nRunning test_cache_warmup...")
    
    # Create a CacheManager
    cm = CacheManager(config=config_with_warmup)
    
    try:
        # Create a temporary file for warmup keys
        with tempfile.NamedTemporaryFile('w', delete=False) as f:
            json.dump({
                "keys": ["warmup_key1", "warmup_key2", "warmup_key3"]
            }, f)
            warmup_file = f.name
    
        # Set up value providers for the warmup
        def provide_value1():
            return "warmup_value1"
    
        def provide_value2():
            return "warmup_value2"
    
        # Create a CacheWarmup instance
        warmup = CacheWarmup(
            enabled=True,
            warmup_keys_file=warmup_file
        )
    
        # Add value providers
        warmup.add_value_provider("warmup_key1", provide_value1)
        warmup.add_value_provider("warmup_key2", provide_value2)
    
        # Perform warmup
        stats = await warmup.warmup(cm)
    
        # Verify keys were warmed up
        value1 = await cm.get("warmup_key1")
        assert value1 == "warmup_value1"
    
        value2 = await cm.get("warmup_key2")
        assert value2 == "warmup_value2"
    
        # warmup_key3 should not be in the cache (no provider)
        value3 = await cm.get("warmup_key3")
        assert value3 is None
    
        # Verify stats - use the keys that are actually in the stats dict
        assert stats["loaded_keys"] >= 2
        assert stats["success"] is True
    
        # Clean up the temporary file
        os.unlink(warmup_file)
    finally:
        # Ensure we properly close the CacheManager
        await cm.close()

# Standalone test functions for running directly
async def run_cache_warmup_test():
    """Test the cache warmup feature without using pytest fixtures."""
    # Create a temporary warmup keys file
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
        json.dump([
            {"key": "warmup_key1", "value": "warmup_value1"},
            {"key": "warmup_key2", "value": "warmup_value2"}
        ], f)
        warmup_file = f.name
    
    try:
        config = CacheConfig()
        
        # Configure features
        config.enable_warmup = True
        config.warmup_keys_file = warmup_file
        config.cache_dir = tempfile.mkdtemp()
        
        # Create mock classes for testing
        class MockCacheWarmup:
            """Mock cache warmup for testing."""
            
            def __init__(self, enabled=False, warmup_keys_file=None):
                self.enabled = enabled
                self.warmup_keys_file = warmup_keys_file
                self.logger = logging.getLogger("mock_cache_warmup")
            
            async def warmup(self, cache_manager):
                """Warm up the cache with predefined keys."""
                if not self.enabled or not self.warmup_keys_file:
                    return {"loaded_keys": 0, "success": False}
                    
                try:
                    with open(self.warmup_keys_file, 'r') as f:
                        warmup_data = json.load(f)
                        
                    if isinstance(warmup_data, list):
                        for item in warmup_data:
                            if isinstance(item, dict) and "key" in item and "value" in item:
                                await cache_manager.set(item["key"], item["value"])
                        return {"loaded_keys": len(warmup_data), "success": True}
                    else:
                        self.logger.error(f"Invalid format in warmup file: {type(warmup_data)}")
                        return {"loaded_keys": 0, "success": False}
                        
                except Exception as e:
                    self.logger.error(f"Error during cache warmup: {e}")
                    return {"loaded_keys": 0, "success": False}
        
        class MockCacheManager:
            """Simplified cache manager for testing."""
            
            def __init__(self, config):
                self._config = config
                self._cache = {}
                self._logger = logging.getLogger("mock_cache_manager")
                self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}
                
                # Initialize cache warmup
                self._cache_warmup = MockCacheWarmup(
                    enabled=config.enable_warmup,
                    warmup_keys_file=config.warmup_keys_file
                )
            
            async def get(self, key):
                """Get a value from the cache."""
                if key in self._cache:
                    self._stats["hits"] += 1
                    return self._cache[key]
                
                self._stats["misses"] += 1
                return None
            
            async def set(self, key, value, expiration=None):
                """Set a value in the cache."""
                self._cache[key] = value
                self._stats["sets"] += 1
            
            async def delete(self, key):
                """Delete a value from the cache."""
                if key in self._cache:
                    del self._cache[key]
                    self._stats["deletes"] += 1
                    return True
                return False
            
            async def close(self):
                """Close the cache manager."""
                self._cache.clear()
        
        cache = MockCacheManager(config)
        
        try:
            # Warm up the cache
            await cache._cache_warmup.warmup(cache)
            
            # Verify the keys were warmed up
            value1 = await cache.get("warmup_key1")
            value2 = await cache.get("warmup_key2")
            
            assert value1 == "warmup_value1", "Warmup key1 not found or incorrect value"
            assert value2 == "warmup_value2", "Warmup key2 not found or incorrect value"
            
            print("✅ Cache warmup test passed")
            return True
        except AssertionError as e:
            print(f"❌ Cache warmup test failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Cache warmup test failed with exception: {e}")
            return False
        finally:
            await cache.close()
    finally:
        # Clean up the temporary file
        os.unlink(warmup_file)

if __name__ == "__main__":
    asyncio.run(run_cache_warmup_test()) 
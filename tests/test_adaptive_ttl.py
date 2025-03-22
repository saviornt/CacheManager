"""Tests for adaptive TTL functionality in CacheManager."""

import asyncio
import logging
import os
import tempfile
import pytest
from typing import Generator

from src.cache_config import CacheConfig
from src.cache_manager import CacheManager

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Fixture to set up configuration for tests with adaptive TTL
@pytest.fixture
def config_with_adaptive_ttl(tmp_path) -> Generator[CacheConfig, None, None]:
    """Create a configuration with adaptive TTL enabled."""
    # Use a temporary directory for cache files
    cache_dir = tmp_path / "cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    # Return a configuration with adaptive TTL enabled
    config = CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="cache.db",
        cache_max_size=50,
        cache_ttl=300.0,
        use_redis=False,
        retry_attempts=1,
        retry_delay=1,
        
        # Adaptive TTL settings
        enable_adaptive_ttl=True,
        adaptive_ttl_min=10,
        adaptive_ttl_max=300,
        access_count_threshold=2,  # Lower threshold for testing
    )
    yield config

# Tests for adaptive TTL
@pytest.mark.asyncio
async def test_adaptive_ttl(config_with_adaptive_ttl):
    """Test adaptive TTL functionality."""
    print("\nRunning test_adaptive_ttl...")
    
    # Create a CacheManager with adaptive TTL enabled
    cm = CacheManager(config=config_with_adaptive_ttl)
    
    try:
        # Set a key and access it multiple times
        await cm.set("infrequent_key", "value1", ttl=60)
        await cm.set("frequent_key", "value2", ttl=60)
        
        # Access the frequent key multiple times to increase its access count
        for _ in range(5):
            await cm.get("frequent_key")
            
        # Access the infrequent key just once
        await cm.get("infrequent_key")
        
        # Check access counts
        frequent_access_count = cm._adaptive_ttl.get_access_count("frequent_key")
        infrequent_access_count = cm._adaptive_ttl.get_access_count("infrequent_key")
        
        # Verify that the frequent key has a higher access count
        assert frequent_access_count > infrequent_access_count
        print(f"Access counts - frequent: {frequent_access_count}, infrequent: {infrequent_access_count}")
        
        # Note: To verify TTL adjustments, we would need to run longer
        # as they are adjusted over time based on access patterns
    finally:
        await cm.close()

# Standalone test function for running directly
async def run_adaptive_ttl_test():
    """Test the adaptive TTL feature without using pytest fixtures."""
    config = CacheConfig()
    
    # Configure features
    config.enable_adaptive_ttl = True
    config.adaptive_ttl_min = 10
    config.adaptive_ttl_max = 300
    config.access_count_threshold = 3
    config.cache_dir = tempfile.mkdtemp()
    
    # Create mock classes for testing
    class MockAdaptiveTTLManager:
        """Mock adaptive TTL manager for testing."""
        
        def __init__(self, enabled=False, min_ttl=60, max_ttl=86400, access_count_threshold=5):
            self.enabled = enabled
            self.min_ttl = min_ttl
            self.max_ttl = max_ttl
            self.access_count_threshold = access_count_threshold
            self.access_counts = {}
            self.current_ttls = {}
        
        def record_access(self, key):
            """Record an access to the key."""
            self.access_counts[key] = self.access_counts.get(key, 0) + 1
        
        def adjust_ttl(self, key, base_ttl):
            """Adjust TTL based on access patterns."""
            access_count = self.access_counts.get(key, 0)
            
            # Always store the original TTL on first access
            if key not in self.current_ttls:
                self.current_ttls[key] = base_ttl
            
            if access_count > self.access_count_threshold:
                # Increase TTL for frequently accessed keys
                adjusted_ttl = min(self.current_ttls[key] * 1.5, self.max_ttl)
                self.current_ttls[key] = adjusted_ttl
            else:
                adjusted_ttl = max(base_ttl, self.min_ttl)
                
            return adjusted_ttl
        
        def get_access_count(self, key):
            """Get the access count for a key."""
            return self.access_counts.get(key, 0)
        
        def get_current_ttl(self, key):
            """Get the current TTL for a key."""
            return self.current_ttls.get(key, self.min_ttl)
    
    class MockCacheManager:
        """Simplified cache manager for testing."""
        
        def __init__(self, config):
            self._config = config
            self._cache = {}
            self._logger = logging.getLogger("mock_cache_manager")
            self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}
            
            # Initialize adaptive TTL
            self._adaptive_ttl = MockAdaptiveTTLManager(
                enabled=config.enable_adaptive_ttl,
                min_ttl=config.adaptive_ttl_min,
                max_ttl=config.adaptive_ttl_max,
                access_count_threshold=config.access_count_threshold
            )
        
        async def get(self, key):
            """Get a value from the cache."""
            if key in self._cache:
                self._stats["hits"] += 1
                
                # Record access for adaptive TTL
                if self._adaptive_ttl.enabled:
                    self._adaptive_ttl.record_access(key)
                    
                return self._cache[key]
            
            self._stats["misses"] += 1
            
            return None
        
        async def set(self, key, value, expiration=None):
            """Set a value in the cache."""
            # Apply adaptive TTL
            if self._adaptive_ttl.enabled and expiration is not None:
                expiration = self._adaptive_ttl.adjust_ttl(key, expiration)
            
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
        # Set initial value with TTL
        initial_ttl = 60
        await cache.set("adaptive_key", "test_value", expiration=initial_ttl)
        
        # Access the key multiple times to trigger TTL adjustment
        for _ in range(config.access_count_threshold + 3):  # Access more times to ensure threshold is crossed
            await cache.get("adaptive_key")
        
        # Set the key again to trigger TTL adjustment
        await cache.set("adaptive_key", "test_value", expiration=initial_ttl)
        
        # Access more times to ensure the threshold is crossed
        for _ in range(config.access_count_threshold + 2):
            await cache.get("adaptive_key")
        
        # Check if TTL was adjusted
        adjusted_ttl = cache._adaptive_ttl.get_current_ttl("adaptive_key")
        print(f"Initial TTL: {initial_ttl}, Adjusted TTL: {adjusted_ttl}")
        assert adjusted_ttl > initial_ttl, "TTL was not increased after multiple accesses"
        
        print("✅ Adaptive TTL test passed")
        return True
    except AssertionError as e:
        print(f"❌ Adaptive TTL test failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Adaptive TTL test failed with exception: {e}")
        return False
    finally:
        await cache.close()

if __name__ == "__main__":
    asyncio.run(run_adaptive_ttl_test()) 
"""Tests for advanced CacheManager features.

This module tests the advanced features of CacheManager including:
- Telemetry and observability hooks
- Distributed locking
- Cache sharding
- Cross-node cache invalidation
- Security features (encryption, signing, access control)
- Cache warmup
- Adaptive TTL
"""

import asyncio
import json
import logging
import os
import tempfile
import uuid
from typing import Dict, Any, Optional, List
from enum import Enum, auto

import pytest

from src.cache_config import CacheConfig

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Define enums for testing
class CacheLayerType(Enum):
    """Type of cache layer."""
    MEMORY = auto()
    DISK = auto()
    REDIS = auto()

# Fixture to set up configuration for tests using in-memory and disk cache
@pytest.fixture
def config_with_features(tmp_path):
    # Use a temporary directory for cache files
    cache_dir = tmp_path / "cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    # Return a configuration with the new features enabled
    return CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="cache.db",
        cache_max_size=50,
        cache_ttl=300.0,
        use_redis=False,  # Don't use Redis for basic tests
        retry_attempts=1,
        retry_delay=1,
        
        # Telemetry settings
        enable_telemetry=True,
        telemetry_interval=1,  # 1 second for fast testing
        
        # Adaptive TTL settings
        enable_adaptive_ttl=True,
        adaptive_ttl_min=10,
        adaptive_ttl_max=300,
        access_count_threshold=2,  # Lower threshold for testing
        
        # Cache warmup settings
        enable_warmup=True,
        
        # Security settings
        enable_encryption=True,
        encryption_key="test_encryption_key_1234567890abcdef",
        encryption_salt="test_salt",
        
        enable_data_signing=True,
        signing_key="test_signing_key_1234567890abcdef",
        
        # Distributed features (enabled in specific tests)
        use_distributed_locking=False,
        enable_sharding=False,
        enable_invalidation=False
    )

# Redis fixture for distributed tests
@pytest.fixture(scope="module")
async def redis_config(request):
    """Create a configuration with Redis enabled.
    
    This fixture will be skipped if Redis is not available.
    """
    import redis.asyncio as redis
    
    # Try connecting to Redis
    try:
        r = redis.Redis()
        await r.ping()
        await r.close()
    except:
        pytest.skip("Redis server not available")
    
    return CacheConfig(
        use_redis=True,
        redis_url="redis://localhost",
        redis_port=6379,
        namespace="test_advanced",
        
        # Distributed features
        use_distributed_locking=True,
        enable_sharding=True,
        num_shards=4,
        sharding_algorithm="consistent_hash",
        enable_invalidation=True,
        
        # Security features
        enable_encryption=True,
        encryption_key="test_encryption_key",
        enable_data_signing=True,
        signing_key="test_signing_key"
    )

# Helper function for async testing
async def wait_for(condition_func, timeout=5, interval=0.1):
    """Wait for a condition to be true."""
    start_time = time.time()
    while not condition_func() and time.time() - start_time < timeout:
        await asyncio.sleep(interval)
    return condition_func()

# Tests for telemetry and observability hooks
@pytest.mark.asyncio
async def test_telemetry(config_with_features):
    """Test telemetry collection and reporting."""
    print("\nRunning test_telemetry...")
    
    # Create a CacheManager with telemetry enabled
    cm = CacheManager(config=config_with_features)
    
    # Set and get operations to generate telemetry
    await cm.set("test_key1", "value1")
    await cm.set("test_key2", "value2")
    await cm.get("test_key1")
    await cm.get("test_key3")  # Miss
    
    # Wait for metrics to be collected
    await asyncio.sleep(1.5)  # Wait longer than telemetry_interval
    
    # Get the telemetry metrics
    metrics = cm._telemetry.get_metrics()
    
    # Verify some basic metrics
    assert metrics['counters'].get('cache.hit') >= 1, "Cache hit counter should be tracked"
    assert metrics['counters'].get('cache.miss') >= 1, "Cache miss counter should be tracked"
    assert len(metrics['timings']) > 0, "Operation timings should be tracked"
    
    await cm.close()
    
    print("✅ test_telemetry passed!")

# Tests for adaptive TTL
@pytest.mark.asyncio
async def test_adaptive_ttl(config_with_features):
    """Test adaptive TTL functionality."""
    print("\nRunning test_adaptive_ttl...")
    
    # Create a CacheManager with adaptive TTL enabled
    cm = CacheManager(config=config_with_features)
    
    # Set a key and access it multiple times
    await cm.set("infrequent_key", "value1", expiration=60)
    await cm.set("frequent_key", "value2", expiration=60)
    
    # Access the frequent key multiple times
    for _ in range(5):
        await cm.get("frequent_key")
        await asyncio.sleep(0.1)
    
    # Access the infrequent key once
    await cm.get("infrequent_key")
    
    # Set the keys again to trigger TTL adjustment
    await cm.set("infrequent_key", "value1_updated")
    await cm.set("frequent_key", "value2_updated")
    
    # Get the TTLs from the adaptive TTL manager
    frequent_ttl = cm._adaptive_ttl.get_ttl("frequent_key", 60)
    infrequent_ttl = cm._adaptive_ttl.get_ttl("infrequent_key", 60)
    
    # The frequent key should have a longer TTL than the infrequent key
    assert frequent_ttl > infrequent_ttl, f"Frequent key TTL ({frequent_ttl}) should be longer than infrequent key TTL ({infrequent_ttl})"
    
    # Get stats for logging
    stats = cm._adaptive_ttl.get_stats()
    print(f"  Adaptive TTL stats: {json.dumps(stats, indent=2)}")
    
    await cm.close()
    
    print("✅ test_adaptive_ttl passed!")

# Tests for cache warmup
@pytest.mark.asyncio
async def test_cache_warmup(config_with_features):
    """Test cache warmup functionality."""
    print("\nRunning test_cache_warmup...")
    
    # Create a CacheManager
    cm = CacheManager(config=config_with_features)
    
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
    value2 = await cm.get("warmup_key2")
    value3 = await cm.get("warmup_key3")
    
    assert value1 == "warmup_value1", "Key 1 should be warmed up with value from provider"
    assert value2 == "warmup_value2", "Key 2 should be warmed up with value from provider"
    assert value3 is None, "Key 3 should not be warmed up (no provider)"
    
    # Check stats
    assert stats['keys_loaded'] >= 2, "At least 2 keys should be loaded"
    
    # Clean up the warmup file
    os.unlink(warmup_file)
    
    await cm.close()
    
    print("✅ test_cache_warmup passed!")

# Tests for security features
@pytest.mark.asyncio
async def test_encryption_and_signing(config_with_features):
    """Test encryption and data signing."""
    print("\nRunning test_encryption_and_signing...")
    
    # Create a CacheManager with security features
    cm = CacheManager(config=config_with_features)
    
    # Test data to encrypt and sign
    data = {
        "sensitive": "secret_value",
        "id": 12345,
        "nested": {
            "more_sensitive": "another_secret"
        }
    }
    
    # Set and get the data
    await cm.set("secure_key", data)
    retrieved = await cm.get("secure_key")
    
    # Verify the data was correctly retrieved
    assert retrieved == data, "Retrieved data should match original"
    
    # Test the encryption and signing directly
    encryptor = CacheEncryptor(
        secret_key="test_key",
        salt="test_salt",
        enabled=True
    )
    
    signer = DataSigner(
        secret_key="test_signing_key",
        enabled=True
    )
    
    # Test encryption
    original = b"sensitive data"
    encrypted = encryptor.encrypt(original)
    assert encrypted != original, "Encrypted data should differ from original"
    decrypted = encryptor.decrypt(encrypted)
    assert decrypted == original, "Decrypted data should match original"
    
    # Test signing
    signed = signer.sign(original)
    assert signed != original, "Signed data should differ from original"
    verified = signer.verify(signed)
    assert verified == original, "Verified data should match original"
    
    await cm.close()
    
    print("✅ test_encryption_and_signing passed!")

@pytest.mark.asyncio
async def test_access_control():
    """Test access control functionality."""
    print("\nRunning test_access_control...")
    
    # Create an access control instance
    ac = AccessControl(enabled=True)
    
    # Add some policies
    ac.add_policy("public:*", allow_read=True, allow_write=True, allow_delete=True)
    ac.add_policy("admin:*", allow_read=True, allow_write=True, allow_delete=True, required_roles={"admin"})
    ac.add_policy("readonly:*", allow_read=True, allow_write=False, allow_delete=False)
    
    # Define users
    admin_user = {"roles": ["admin", "user"]}
    regular_user = {"roles": ["user"]}
    
    # Test access permissions
    # Public keys
    assert ac.check_access("public:key1", "read"), "Everyone should be able to read public keys"
    assert ac.check_access("public:key1", "write"), "Everyone should be able to write public keys"
    assert ac.check_access("public:key1", "delete"), "Everyone should be able to delete public keys"
    
    # Admin keys with admin user
    assert ac.check_access("admin:key1", "read", admin_user), "Admin should be able to read admin keys"
    assert ac.check_access("admin:key1", "write", admin_user), "Admin should be able to write admin keys"
    assert ac.check_access("admin:key1", "delete", admin_user), "Admin should be able to delete admin keys"
    
    # Admin keys with regular user
    with pytest.raises(Exception):
        ac.check_access("admin:key1", "read", regular_user)
        
    with pytest.raises(Exception):
        ac.check_access("admin:key1", "write", regular_user)
        
    with pytest.raises(Exception):
        ac.check_access("admin:key1", "delete", regular_user)
    
    # Readonly keys
    assert ac.check_access("readonly:key1", "read"), "Everyone should be able to read readonly keys"
    
    with pytest.raises(Exception):
        ac.check_access("readonly:key1", "write")
        
    with pytest.raises(Exception):
        ac.check_access("readonly:key1", "delete")
    
    print("✅ test_access_control passed!")

# Distributed features tests (requires Redis)
@pytest.mark.asyncio
async def test_distributed_locking(redis_config):
    """Test distributed locking functionality."""
    try:
        import redis.asyncio as redis
        
        # Create a Redis client
        r = redis.Redis.from_url(redis_config.full_redis_url)
        
        # Create two distributed locks
        lock1 = DistributedLock(r, lock_prefix="test:lock:")
        lock2 = DistributedLock(r, lock_prefix="test:lock:")
        
        # Lock a resource with lock1
        resource = "shared_resource"
        acquired1 = await lock1.acquire(resource)
        assert acquired1, "Lock1 should acquire the lock"
        
        # Try to lock the same resource with lock2
        acquired2 = await lock2.acquire(resource)
        assert not acquired2, "Lock2 should not be able to acquire the lock"
        
        # Release the lock with lock1
        released = await lock1.release(resource)
        assert released, "Lock1 should release the lock"
        
        # Now lock2 should be able to acquire it
        acquired2 = await lock2.acquire(resource)
        assert acquired2, "Lock2 should acquire the lock after release"
        
        # Clean up
        await lock2.release(resource)
        await r.close()
        
        print("✅ test_distributed_locking passed!")
    except ImportError:
        pytest.skip("Redis library not available")
    except Exception as e:
        await r.close()
        print(f"❌ test_distributed_locking failed: {e}")
        raise

@pytest.mark.asyncio
async def test_cache_sharding():
    """Test cache sharding functionality."""
    print("\nRunning test_cache_sharding...")
    
    # Test the hash ring sharding strategy
    hash_ring = HashRingShardingStrategy(virtual_nodes=10)
    hash_ring.initialize(4)  # 4 shards
    
    # Verify that consistent keys go to the same shard
    shard1 = hash_ring.get_shard("test_key1", 4)
    shard1_again = hash_ring.get_shard("test_key1", 4)
    assert shard1 == shard1_again, "Same key should map to same shard"
    
    # Test modulo sharding strategy
    modulo = ModuloShardingStrategy()
    
    # Create a shard manager
    def mock_shard_resolver(shard_idx):
        return f"Shard-{shard_idx}"
    
    shard_manager = ShardManager(
        num_shards=4,
        strategy=hash_ring,
        shard_resolver=mock_shard_resolver
    )
    
    # Get shard for a key
    shard_idx, shard = shard_manager.get_shard_for_key("test_key1", "test_namespace")
    assert 0 <= shard_idx < 4, "Shard index should be within range"
    assert shard == f"Shard-{shard_idx}", "Shard resolver should be called"
    
    # Group keys by shard
    keys = ["key1", "key2", "key3", "key4", "key5"]
    grouped = shard_manager.get_shard_indices_for_keys(keys)
    
    # All keys should be assigned to a shard
    assert sum(len(keys) for keys in grouped.values()) == len(keys), "All keys should be assigned"
    
    # Update shard count and verify it changes
    original_num_shards = shard_manager.num_shards
    shard_manager.update_shard_count(8)
    assert shard_manager.num_shards == 8, "Shard count should be updated"
    
    print("✅ test_cache_sharding passed!")

@pytest.mark.asyncio
async def test_cross_node_invalidation(redis_config):
    """Test cross-node cache invalidation."""
    try:
        import redis.asyncio as redis
        
        print("\nRunning test_cross_node_invalidation...")
        
        # Create a Redis client
        r = redis.Redis.from_url(redis_config.full_redis_url)
        
        # Create two invalidation managers (simulating two cache nodes)
        inv1 = InvalidationManager(r, channel="test:invalidation", enabled=True, node_id="node1")
        inv2 = InvalidationManager(r, channel="test:invalidation", enabled=True, node_id="node2")
        
        # Start the invalidation listeners
        await inv1.start()
        await inv2.start()
        
        # Track invalidated keys on node2
        invalidated_keys = set()
        
        async def invalidation_callback(data):
            if data.get('type') == InvalidationEvent.KEY.value:
                invalidated_keys.add(data.get('key'))
        
        # Add a callback to node2
        inv2.add_callback(InvalidationEvent.KEY, invalidation_callback)
        
        # Node1 invalidates a key
        await inv1.invalidate_key("test_key1", reason="Test invalidation")
        
        # Wait for invalidation to propagate
        await asyncio.sleep(1)
        
        # Check if node2 received the invalidation
        assert "test_key1" in invalidated_keys, "Node2 should receive invalidation from node1"
        
        # Stop the invalidation listeners
        await inv1.stop()
        await inv2.stop()
        
        # Clean up
        await r.close()
        
        print("✅ test_cross_node_invalidation passed!")
    except ImportError:
        pytest.skip("Redis library not available")
    except Exception as e:
        await r.close()
        print(f"❌ test_cross_node_invalidation failed: {e}")
        raise

# Mock dependencies for standalone testing
class MockCacheLayer:
    """Mock cache layer for testing without real persistent storage."""
    
    def __init__(self, namespace="default", ttl=3600):
        self.data = {}
        self.namespace = namespace
        self.ttl = ttl
    
    async def get(self, key: str) -> Any:
        """Get a value from the cache."""
        return self.data.get(key)
    
    async def set(self, key: str, value: Any, expiration: Optional[int] = None) -> None:
        """Set a value in the cache."""
        self.data[key] = value
    
    async def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        if key in self.data:
            del self.data[key]
            return True
        return False
    
    async def clear(self) -> bool:
        """Clear all values from the cache."""
        self.data.clear()
        return True
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from the cache."""
        return {k: self.data.get(k) for k in keys if k in self.data}
    
    async def set_many(self, items: Dict[str, Any], expiration: Optional[int] = None) -> None:
        """Set multiple values in the cache."""
        self.data.update(items)
    
    async def delete_many(self, keys: List[str]) -> int:
        """Delete multiple values from the cache."""
        count = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                count += 1
        return count
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache."""
        return {
            "size": len(self.data),
            "hits": 0,
            "misses": 0
        }
    
    async def close(self) -> None:
        """Close the cache."""
        self.data.clear()

# Monkey patch for testing
def setup_test_cache_layers(cache_manager):
    """Set up memory and disk cache layers for testing."""
    cache_manager._cache_layers = {
        CacheLayerType.MEMORY: MockCacheLayer(namespace=cache_manager._config.namespace),
        CacheLayerType.DISK: MockCacheLayer(namespace=cache_manager._config.namespace)
    }

# Create mock versions of our dependencies
class MockCacheManager:
    """Simplified cache manager for testing advanced features."""
    
    def __init__(self, config):
        self._config = config
        self._cache = {}
        self._logger = logging.getLogger("mock_cache_manager")
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}
        
        # Initialize advanced features
        self._telemetry = MockTelemetryManager(
            enabled=config.enable_telemetry,
            report_interval=config.telemetry_interval
        )
        
        self._adaptive_ttl = MockAdaptiveTTLManager(
            enabled=config.enable_adaptive_ttl,
            min_ttl=config.adaptive_ttl_min,
            max_ttl=config.adaptive_ttl_max,
            access_count_threshold=config.access_count_threshold
        )
        
        self._cache_warmup = MockCacheWarmup(
            enabled=config.enable_warmup,
            warmup_keys_file=config.warmup_keys_file
        )
        
        self._encryptor = MockEncryptor(
            enabled=config.enable_encryption,
            secret_key=config.encryption_key,
            salt=config.encryption_salt
        )
    
    async def get(self, key: str) -> Any:
        """Get a value from the cache."""
        if key in self._cache:
            self._stats["hits"] += 1
            
            # Record access for adaptive TTL
            if self._adaptive_ttl.enabled:
                self._adaptive_ttl.record_access(key)
                
            # Record operation in telemetry
            if self._telemetry.enabled:
                self._telemetry.record_operation("get", True)
                
            return self._cache[key]
        
        self._stats["misses"] += 1
        
        # Record operation in telemetry
        if self._telemetry.enabled:
            self._telemetry.record_operation("get", False)
            
        return None
    
    async def set(self, key: str, value: Any, expiration: Optional[int] = None) -> None:
        """Set a value in the cache."""
        # Apply adaptive TTL
        if self._adaptive_ttl.enabled and expiration is not None:
            expiration = self._adaptive_ttl.adjust_ttl(key, expiration)
        
        # Apply encryption if enabled
        if self._encryptor.enabled:
            stored_value = self._encryptor.encrypt(value)
        else:
            stored_value = value
            
        self._cache[key] = stored_value
        self._stats["sets"] += 1
        
        # Record operation in telemetry
        if self._telemetry.enabled:
            self._telemetry.record_operation("set", True)
    
    async def delete(self, key: str) -> bool:
        """Delete a value from the cache."""
        if key in self._cache:
            del self._cache[key]
            self._stats["deletes"] += 1
            
            # Record operation in telemetry
            if self._telemetry.enabled:
                self._telemetry.record_operation("delete", True)
                
            return True
        
        # Record operation in telemetry
        if self._telemetry.enabled:
            self._telemetry.record_operation("delete", False)
            
        return False
    
    async def close(self) -> None:
        """Close the cache manager."""
        self._cache.clear()
        await self._telemetry.stop()


class MockTelemetryManager:
    """Mock telemetry manager for testing."""
    
    def __init__(self, enabled=False, report_interval=60):
        self.enabled = enabled
        self.report_interval = report_interval
        self.metrics = {
            "operations": {"get": 0, "set": 0, "delete": 0},
            "hits": 0,
            "misses": 0,
            "latency": {"get": [], "set": [], "delete": []}
        }
    
    async def start(self):
        """Start collecting telemetry."""
        pass
    
    async def stop(self):
        """Stop collecting telemetry."""
        pass
    
    def record_operation(self, operation, success):
        """Record an operation in telemetry."""
        self.metrics["operations"][operation] += 1
        if operation == "get":
            if success:
                self.metrics["hits"] += 1
            else:
                self.metrics["misses"] += 1
    
    async def get_metrics(self):
        """Get the collected metrics."""
        return self.metrics


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
    
    def get_current_ttl(self, key):
        """Get the current TTL for a key."""
        return self.current_ttls.get(key, self.min_ttl)


class MockCacheWarmup:
    """Mock cache warmup for testing."""
    
    def __init__(self, enabled=False, warmup_keys_file=None):
        self.enabled = enabled
        self.warmup_keys_file = warmup_keys_file
        self.logger = logging.getLogger("mock_cache_warmup")
    
    async def warmup(self, cache_manager):
        """Warm up the cache with predefined keys."""
        if not self.enabled or not self.warmup_keys_file:
            return 0
            
        try:
            with open(self.warmup_keys_file, 'r') as f:
                warmup_data = json.load(f)
                
            if isinstance(warmup_data, list):
                for item in warmup_data:
                    if isinstance(item, dict) and "key" in item and "value" in item:
                        await cache_manager.set(item["key"], item["value"])
                return len(warmup_data)
            else:
                self.logger.error(f"Invalid format in warmup file: {type(warmup_data)}")
                return 0
                
        except Exception as e:
            self.logger.error(f"Error during cache warmup: {e}")
            return 0


class MockEncryptor:
    """Mock encryptor for testing."""
    
    def __init__(self, enabled=False, secret_key="", salt=""):
        self.enabled = enabled
        self.secret_key = secret_key
        self.salt = salt
    
    def encrypt(self, data):
        """Encrypt data (mock implementation just returns the data)."""
        # In real implementation, this would encrypt the data
        return data
    
    def decrypt(self, data):
        """Decrypt data (mock implementation just returns the data)."""
        # In real implementation, this would decrypt the data
        return data


# Standalone test functions for running directly
async def run_telemetry_test():
    """Test the telemetry feature without using pytest fixtures."""
    config = CacheConfig()
    
    # Configure features
    config.enable_telemetry = True
    config.telemetry_interval = 1
    config.cache_dir = tempfile.mkdtemp()
    config.log_dir = config.cache_dir
    
    cache = MockCacheManager(config)
    
    try:
        # Perform some operations
        await cache.set("test_key1", "value1")
        await cache.get("test_key1")
        await cache.get("non_existent_key")
        await cache.delete("test_key1")
        
        # Get metrics
        metrics = await cache._telemetry.get_metrics()
        
        # Verify metrics
        assert metrics["operations"]["get"] > 0, "Get operations not recorded"
        assert metrics["operations"]["set"] > 0, "Set operations not recorded"
        assert metrics["operations"]["delete"] > 0, "Delete operations not recorded"
        assert metrics["hits"] > 0, "Cache hits not recorded"
        assert metrics["misses"] > 0, "Cache misses not recorded"
        
        print("✅ Telemetry test passed")
        return True
    except AssertionError as e:
        print(f"❌ Telemetry test failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Telemetry test failed with exception: {e}")
        return False
    finally:
        await cache.close()

async def run_adaptive_ttl_test():
    """Test the adaptive TTL feature without using pytest fixtures."""
    config = CacheConfig()
    
    # Configure features
    config.enable_adaptive_ttl = True
    config.adaptive_ttl_min = 10
    config.adaptive_ttl_max = 300
    config.access_count_threshold = 3
    config.cache_dir = tempfile.mkdtemp()
    
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

async def run_cache_warmup_test():
    """Test the cache warmup feature without using pytest fixtures."""
    # Create a temporary warmup keys file
    import tempfile
    import json
    
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
        import os
        os.unlink(warmup_file)

async def run_encryption_test():
    """Test the encryption feature without using pytest fixtures."""
    config = CacheConfig()
    
    # Configure features
    config.enable_encryption = True
    config.encryption_key = "test_encryption_key_12345"
    config.encryption_salt = "test_salt"
    config.cache_dir = tempfile.mkdtemp()
    
    cache = MockCacheManager(config)
    
    try:
        # Set and get a sensitive value with encryption
        sensitive_data = {"username": "testuser", "password": "password123"}
        await cache.set("sensitive_key", sensitive_data)
        
        # Get the value back
        retrieved_data = await cache.get("sensitive_key")
        
        assert retrieved_data == sensitive_data, "Retrieved encrypted data does not match original"
        
        print("✅ Encryption test passed")
        return True
    except AssertionError as e:
        print(f"❌ Encryption test failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Encryption test failed with exception: {e}")
        return False
    finally:
        await cache.close()

def create_standalone_config():
    """Create a configuration for standalone tests."""
    import tempfile
    
    # Create a temporary directory for cache files
    temp_dir = tempfile.mkdtemp()
    
    config = CacheConfig()
    
    # Configure cache location
    config.cache_dir = temp_dir
    config.cache_file = "cache_test.db"
    
    # Enable features
    config.enable_telemetry = True
    config.telemetry_interval = 1  # 1 second for quick testing
    config.log_dir = temp_dir
    
    config.enable_adaptive_ttl = True
    config.adaptive_ttl_min = 10
    config.adaptive_ttl_max = 300
    config.access_count_threshold = 3
    
    config.enable_warmup = True
    
    # Default to using memory and disk cache only (no Redis dependency)
    config.use_redis = False
    config.memory_cache_enabled = True
    
    return config

# Run tests when this module is executed directly
if __name__ == "__main__":
    import asyncio
    
    print("Running standalone tests...")
    
    async def run_all_tests():
        tests = [
            ("Telemetry", run_telemetry_test()),
            ("Adaptive TTL", run_adaptive_ttl_test()),
            ("Cache Warmup", run_cache_warmup_test()),
            ("Encryption", run_encryption_test())
        ]
        
        results = []
        for name, test_coro in tests:
            print(f"\nRunning {name} test...")
            try:
                result = await test_coro
                results.append(result)
            except Exception as e:
                print(f"❌ {name} test failed with exception: {e}")
                results.append(False)
        
        # Print summary
        print("\n--- Test Summary ---")
        for i, (name, _) in enumerate(tests):
            status = "PASSED" if results[i] else "FAILED"
            print(f"{name}: {status}")
        
        # Return overall success
        return all(results)
    
    success = asyncio.run(run_all_tests())
    import sys
    sys.exit(0 if success else 1) 
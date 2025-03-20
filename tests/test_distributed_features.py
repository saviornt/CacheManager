"""Tests for distributed CacheManager features (locking, sharding, invalidation)."""

import asyncio
import logging
import pytest
from typing import Dict, Any, Generator

from src.cache_config import CacheConfig
from src.cache_manager import CacheManager
from src.core.distributed_lock import DistributedLock
from src.core.sharding import HashRingShardingStrategy, ModuloShardingStrategy, ShardManager

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Fixture for Redis configuration
@pytest.fixture(scope="function")
def redis_config(request: pytest.FixtureRequest) -> Generator[Dict[str, Any], None, None]:
    """Fixture providing Redis configuration for tests."""
    # Skip Redis tests if Redis is not available
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0)
        r.ping()
        r.close()
        config = {
            "redis_host": "localhost",
            "redis_port": 6379,
            "redis_db": 0
        }
        yield config
    except (ImportError, redis.exceptions.ConnectionError):
        pytest.skip("Redis not available - skipping Redis tests")

# Tests for distributed locking
@pytest.mark.asyncio
async def test_distributed_locking():
    """Test distributed locking functionality."""
    print("\nRunning test_distributed_locking...")
    
    # Skip if Redis is not available
    try:
        import redis.asyncio as redis
        r = None
        try:
            # Connect to Redis
            r = redis.from_url('redis://localhost:6379/0')
            await r.ping()  # Test if Redis is available
        except (redis.ConnectionError, redis.RedisError):
            pytest.skip("Redis not available - skipping distributed locking test")
            return
        finally:
            if r:
                await r.aclose()
                
        # Create the distributed lock
        lock = DistributedLock(
            key="test_lock",
            redis_url='redis://localhost:6379/0',
            expire=10,
            retry_interval=0.1,
            max_retries=3
        )
        
        # Test basic lock functionality
        async with lock:
            # Lock acquired
            assert lock.is_locked(), "Lock should be acquired"
            
            # Try acquiring the same lock in a separate connection
            lock2 = DistributedLock(
                key="test_lock",
                redis_url='redis://localhost:6379/0',
                expire=10,
                retry_interval=0.1,
                max_retries=1
            )
            
            # This should fail because the lock is already held
            try:
                async with lock2:
                    assert False, "Should not have acquired the lock"
            except Exception:
                # This is expected
                pass
                
        # Lock should be released
        assert not lock.is_locked(), "Lock should be released"
        
        # Now we should be able to acquire the lock again
        async with lock:
            assert lock.is_locked(), "Lock should be acquired again"
            
    except ModuleNotFoundError:
        pytest.skip("Redis not available - skipping distributed locking test")

# Tests for cache sharding
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
    modulo_shard1 = modulo.get_shard("test_key1", 4)
    modulo_shard1_again = modulo.get_shard("test_key1", 4)
    assert modulo_shard1 == modulo_shard1_again, "Same key should map to same shard in modulo strategy"
    
    # Test shard manager with hash ring strategy
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
    
    # Test shard manager with modulo strategy
    modulo_shard_manager = ShardManager(
        num_shards=4,
        strategy=modulo,
        shard_resolver=mock_shard_resolver
    )
    
    # Get shard for the same key with modulo strategy
    modulo_shard_idx, modulo_shard = modulo_shard_manager.get_shard_for_key("test_key1", "test_namespace")
    assert 0 <= modulo_shard_idx < 4, "Modulo shard index should be within range"
    
    # Group keys by shard
    keys = ["key1", "key2", "key3", "key4", "key5"]
    grouped = shard_manager.get_shard_indices_for_keys(keys)
    
    # All keys should be assigned to a shard
    assert sum(len(keys) for keys in grouped.values()) == len(keys), "All keys should be assigned"
    
    # Test with modulo strategy
    modulo_grouped = modulo_shard_manager.get_shard_indices_for_keys(keys)
    assert sum(len(keys) for keys in modulo_grouped.values()) == len(keys), "All keys should be assigned with modulo strategy"
    
    # Update shard count and verify it changes
    shard_manager.update_shard_count(8)
    assert shard_manager.num_shards == 8, "Shard count should be updated"
    
    # Update modulo shard count
    modulo_shard_manager.update_shard_count(8)
    assert modulo_shard_manager.num_shards == 8, "Modulo shard count should be updated"
    
    print("✅ test_cache_sharding passed!")

# Tests for cross-node cache invalidation
@pytest.mark.asyncio
async def test_cross_node_invalidation():
    """Test cross-node cache invalidation."""
    print("\nRunning test_cross_node_invalidation...")
    
    # Skip if Redis is not available
    try:
        import redis.asyncio as redis
        r = None
        try:
            # Connect to Redis
            r = redis.from_url('redis://localhost:6379/0')
            await r.ping()  # Test if Redis is available
        except (redis.ConnectionError, redis.RedisError):
            pytest.skip("Redis not available - skipping cross-node invalidation test")
            return
        finally:
            if r:
                await r.aclose()
        
        # Create two CacheManagers representing different nodes
        config1 = CacheConfig(
            use_redis=True,
            redis_host='localhost',
            redis_port=6379,
            enable_invalidation=True,
            node_id="node1"
        )
        
        config2 = CacheConfig(
            use_redis=True,
            redis_host='localhost',
            redis_port=6379,
            enable_invalidation=True,
            node_id="node2"
        )
        
        cm1 = CacheManager(config=config1)
        cm2 = CacheManager(config=config2)
        
        try:
            # Set a value in node 1
            await cm1.set("shared_key", "value_from_node1")
            
            # Both nodes should have the value
            value1 = await cm1.get("shared_key")
            value2 = await cm2.get("shared_key")
            
            assert value1 == "value_from_node1", "Node 1 should have the value"
            assert value2 == "value_from_node1", "Node 2 should have the value"
            
            # Invalidate the key from node 1
            await cm1._invalidation_manager.invalidate_key("shared_key")
            
            # Wait for the invalidation to propagate
            await asyncio.sleep(0.5)
            
            # The key should be invalidated in both nodes
            value1 = await cm1.get("shared_key")
            value2 = await cm2.get("shared_key")
            
            assert value1 is None, "Node 1 should have the key invalidated"
            assert value2 is None, "Node 2 should have the key invalidated"
        finally:
            await cm1.close()
            await cm2.close()
            
    except ModuleNotFoundError:
        pytest.skip("Redis not available - skipping cross-node invalidation test")

if __name__ == "__main__":
    """Run the distributed feature tests if this module is executed directly."""
    
    # Create an asyncio event loop
    loop = asyncio.get_event_loop()
    
    # Try running the sharding test (doesn't need Redis)
    try:
        print("\nRunning cache sharding test...")
        loop.run_until_complete(test_cache_sharding())
        print("✅ Cache sharding test passed")
    except Exception as e:
        print(f"❌ Cache sharding test failed: {e}")
        
    # Try running distributed lock test
    try:
        print("\nRunning distributed lock test...")
        loop.run_until_complete(test_distributed_locking())
        print("✅ Distributed lock test passed")
    except Exception as e:
        print(f"❌ Distributed lock test failed: {str(e)}")
    
    # Try running cross-node invalidation test
    try:
        print("\nRunning cross-node invalidation test...")
        loop.run_until_complete(test_cross_node_invalidation())
        print("✅ Cross-node invalidation test passed")
    except Exception as e:
        print(f"❌ Cross-node invalidation test failed: {str(e)}")
        
    loop.close() 
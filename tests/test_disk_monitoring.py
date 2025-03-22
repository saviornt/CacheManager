"""Tests for disk usage monitoring and automatic cleanup functionality."""

import os
import pytest
import asyncio
import time
from unittest.mock import patch
import shelve

from src.cache_manager import CacheManager
from src.cache_config import CacheConfig, CacheLayerType, CacheLayerConfig


@pytest.fixture
def disk_monitoring_config(tmp_path):
    """Fixture providing cache config with disk monitoring enabled."""
    # Use a temporary directory for cache files
    cache_dir = tmp_path / "cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    # Return a configuration instance with disk monitoring enabled
    return CacheConfig(
        cache_dir=str(cache_dir),
        cache_file="cache.db",
        cache_max_size=100,
        cache_ttl=300.0,
        use_redis=False,
        retry_attempts=1,
        retry_delay=1,
        disk_usage_monitoring=True,
        disk_usage_threshold=75.0,
        disk_critical_threshold=90.0,
        disk_check_interval=1,  # Check every second for testing
        disk_retention_days=30,
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=50),
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=300)
        ]
    )


@pytest.mark.asyncio
async def test_get_disk_usage(disk_monitoring_config):
    """Test the _get_disk_usage method."""
    cm = CacheManager(config=disk_monitoring_config)
    
    # Generate some cache entries to create files
    for i in range(10):
        await cm.set(f"key{i}", f"value{i}" * 100)  # Make values bigger
    
    # Get disk usage
    usage = cm._get_disk_layer_usage()
    
    # Verify results
    assert usage > 0, "Cache size should be greater than 0%"
    assert 0 <= usage <= 100, "Usage percentage should be between 0 and 100"
    
    # Cleanup
    await cm.close()


@pytest.mark.asyncio
async def test_cleanup_disk_cache(disk_monitoring_config):
    """Test the _cleanup_disk_cache method."""
    # Create a cache manager with monitoring disabled to avoid background tasks
    disk_monitoring_config.disk_usage_monitoring = False
    cm = CacheManager(config=disk_monitoring_config)
    
    shelve_file = os.path.join(disk_monitoring_config.cache_dir, disk_monitoring_config.cache_file)
    
    # Add some cache entries with old expiration times
    current_time = time.time()
    past_time = current_time - (35 * 24 * 60 * 60)  # 35 days ago (beyond retention period)
    
    # Use shelve directly to create entries with custom expiration times
    with shelve.open(shelve_file, writeback=True) as db:
        for i in range(20):
            key = cm._namespace_key(f"old_key{i}")
            db[key] = f"old_value{i}"
            expiry_key = f"{key}__expires"
            db[expiry_key] = past_time
    
    # Add some recent entries too
    for i in range(10):
        await cm.set(f"new_key{i}", f"new_value{i}")
    
    # Perform cleanup (non-aggressive)
    removed = await cm._cleanup_disk_cache(aggressive=False)
    
    # Check that old items were removed
    assert removed > 0, "Should have removed old items"
    
    # Verify old items are gone and new items remain
    for i in range(20):
        value = await cm.get(f"old_key{i}")
        assert value is None, f"Old key{i} should have been removed"
    
    for i in range(10):
        value = await cm.get(f"new_key{i}")
        assert value == f"new_value{i}", f"New key{i} should still exist"
    
    # Cleanup
    await cm.close()


@pytest.mark.asyncio
async def test_aggressive_cleanup(disk_monitoring_config):
    """Test aggressive cleanup when disk usage is critical."""
    disk_monitoring_config.disk_usage_monitoring = False
    cm = CacheManager(config=disk_monitoring_config)
    
    # Create many cache items to fill up space
    for i in range(100):
        await cm.set(f"key{i}", f"value{i}" * 1000)  # Make values bigger
    
    # Mock disk_usage to return critical values
    critical_usage = 95.0
    with patch.object(cm, '_get_disk_layer_usage', return_value=critical_usage):
        # Perform aggressive cleanup
        removed = await cm._cleanup_disk_cache(aggressive=True)
        
        # Should have removed items
        assert removed > 0, "Should have removed items during aggressive cleanup"
    
    # Cleanup
    await cm.close()


@pytest.mark.asyncio
async def test_disk_monitoring_task(disk_monitoring_config):
    """Test that the disk monitoring task starts and triggers cleanup appropriately."""
    # Ensure disk monitoring is enabled
    disk_monitoring_config.disk_usage_monitoring = True
    disk_monitoring_config.disk_check_interval = 0.1  # Short interval for testing
    
    # Mock the _cleanup_disk_cache method to check if it gets called
    cleanup_future = asyncio.Future()
    cleanup_future.set_result(10)
    
    with patch('src.cache_manager.CacheManager._cleanup_disk_cache', 
               return_value=cleanup_future) as mock_cleanup:
        
        # Create cache manager with disk monitoring
        cm = CacheManager(config=disk_monitoring_config)
        
        # Manually call _setup_disk_monitoring to ensure the task starts
        cm._setup_disk_monitoring()
        await asyncio.sleep(0.1)
        
        # Mock high disk usage above threshold but below critical
        with patch.object(cm, '_get_disk_layer_usage', return_value=80.0):
            # Wait for the monitoring task to run (using a short interval)
            await asyncio.sleep(0.2)
            
            # Verify cleanup was called with non-aggressive mode
            mock_cleanup.assert_called_with(aggressive=False)
        
        # Now mock critical disk usage
        mock_cleanup.reset_mock()
        
        # Need to create a new future for the second call
        new_future = asyncio.Future()
        new_future.set_result(5)
        mock_cleanup.return_value = new_future
        
        with patch.object(cm, '_get_disk_layer_usage', return_value=95.0):
            # Wait for the monitoring task to run again
            await asyncio.sleep(0.2)
            
            # Verify cleanup was called with aggressive mode
            mock_cleanup.assert_called_with(aggressive=True)
        
        # Cleanup
        if cm._disk_monitor_task:
            cm._disk_monitor_task.cancel()
            try:
                await cm._disk_monitor_task
            except asyncio.CancelledError:
                pass
        
        await cm.close()


@pytest.mark.asyncio
async def test_remove_oldest_items(disk_monitoring_config):
    """Test the _remove_oldest_items method for aggressive cleanup."""
    disk_monitoring_config.disk_usage_monitoring = False
    cm = CacheManager(config=disk_monitoring_config)
    shelve_file = os.path.join(disk_monitoring_config.cache_dir, disk_monitoring_config.cache_file)
    
    # Create items with different timestamps directly in shelve
    now = time.time()
    
    with shelve.open(shelve_file, writeback=True) as db:
        for i in range(10):
            key = cm._namespace_key(f"time_key{i}")
            db[key] = f"time_value{i}"
            expiry_key = f"{key}__expires"
            db[expiry_key] = now - (100 - i * 10)  # Oldest first
    
    # Add more items with current time
    for i in range(10, 20):
        await cm.set(f"time_key{i}", f"time_value{i}")
    
    # Mock high disk usage for first check, then lower after removal
    disk_usage_values = [95.0, 70.0]
    disk_usage_iter = iter(disk_usage_values)
    
    with patch.object(cm, '_get_disk_layer_usage', side_effect=lambda: next(disk_usage_iter)):
        # Remove oldest items
        removed = await cm._remove_oldest_items()
        
        # Should have removed some items
        assert removed > 0, "Should have removed oldest items"
        
        # Check that oldest items are gone
        for i in range(removed):
            value = await cm.get(f"time_key{i}")
            assert value is None, f"Oldest key{i} should have been removed"
    
    # Cleanup
    await cm.close()


@pytest.mark.asyncio
async def test_stats_include_disk_usage(disk_monitoring_config):
    """Test that get_stats includes disk usage information."""
    cm = CacheManager(config=disk_monitoring_config)
    
    # Mock disk usage values
    with patch.object(cm, '_get_disk_layer_usage', return_value=45.5):  # 45.5%
        # Get stats
        stats = cm.get_stats()
        
        # Check disk usage stats are included
        assert "disk_usage_percent" in stats
        assert stats["disk_usage_percent"] == 45.5
    
    # Cleanup
    await cm.close()


@pytest.mark.asyncio
async def test_disk_monitoring_disabled(tmp_path):
    """Test that disk monitoring doesn't start when disabled."""
    # Create config with monitoring disabled
    cache_dir = tmp_path / "cache_disabled"
    os.makedirs(cache_dir, exist_ok=True)
    
    config = CacheConfig(
        cache_dir=str(cache_dir),
        disk_usage_monitoring=False
    )
    
    # Create cache manager
    with patch('asyncio.create_task') as mock_create_task:
        cm = CacheManager(config=config)
        
        # Verify create_task was not called for monitoring
        for call in mock_create_task.call_args_list:
            # Check that none of the calls are for _monitor_disk_usage
            if '_monitor_disk_usage' in str(call):
                assert False, "Monitoring task should not be created when disabled"
    
    # Cleanup
    await cm.close() 
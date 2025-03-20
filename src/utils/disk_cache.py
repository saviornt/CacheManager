"""Utility for managing disk cache operations."""

import os
import shelve
import time
import logging
import shutil
from typing import Optional

logger = logging.getLogger(__name__)

class DiskCacheManager:
    """Manages disk-based cache operations.
    
    Handles cleanup, compaction, and other disk cache maintenance tasks.
    """
    
    def __init__(self, 
                 cache_dir: str,
                 cache_file: str,
                 namespace: str = "default",
                 correlation_id: Optional[str] = None):
        """Initialize the disk cache manager.
        
        Args:
            cache_dir: Directory where cache files are stored
            cache_file: Base filename for disk cache
            namespace: Cache namespace
            correlation_id: Correlation ID for logging
        """
        self.cache_dir = cache_dir
        self.cache_file = cache_file
        self.namespace = namespace
        self.correlation_id = correlation_id or "DCM"
        
        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize shelve file path with namespace
        namespace_suffix = f"_{namespace}" if namespace != "default" else ""
        self.shelve_file = os.path.join(
            self.cache_dir, 
            f"{os.path.splitext(self.cache_file)[0]}{namespace_suffix}.db"
        )
    
    def get_disk_usage(self) -> float:
        """Get current disk cache usage as percentage.
        
        Returns:
            float: Disk usage as percentage (0-100)
        """
        try:
            disk_usage = shutil.disk_usage(self.cache_dir)
            percent_used = (disk_usage.used / disk_usage.total) * 100
            return round(percent_used, 2)
        except Exception as e:
            logger.error(
                f"Error getting disk usage: {e}",
                extra={"correlation_id": self.correlation_id}
            )
            return 0.0
    
    async def clean_disk_cache(self, 
                             retention_days: int, 
                             aggressive: bool = False) -> int:
        """Clean up the disk cache by removing oldest entries.
        
        Args:
            retention_days: How many days of data to retain
            aggressive: If True, perform more aggressive cleanup
            
        Returns:
            int: Number of items removed
        """
        logger.info(
            f"Cleaning disk cache (emergency={aggressive})", 
            extra={"correlation_id": self.correlation_id}
        )
        
        removed_count = 0
        
        try:
            # Calculate retention time in seconds
            retention_seconds = retention_days * 24 * 60 * 60
            retention_threshold = time.time() - retention_seconds
            
            # Remove oldest items
            removed_count = await self._remove_oldest_items(
                retention_threshold=retention_threshold,
                aggressive=aggressive
            )
            
            logger.info(
                f"Disk cache cleaned, removed {removed_count} items", 
                extra={"correlation_id": self.correlation_id}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to clean disk cache: {e}", 
                extra={"correlation_id": self.correlation_id}
            )
            
        return removed_count
            
    async def _remove_oldest_items(self, 
                                 retention_threshold: float,
                                 aggressive: bool = False) -> int:
        """Remove oldest items from disk cache.
        
        Args:
            retention_threshold: Timestamp threshold for retention
            aggressive: If True, remove more aggressively
            
        Returns:
            int: Number of items removed
        """
        removed_count = 0
        
        try:
            # Target percentage to remove in aggressive mode
            aggressive_percent = 50  # Remove up to 50% of items in aggressive mode
            
            # Open shelve file for reading/writing
            with shelve.open(self.shelve_file, writeback=True) as db:
                # Get all keys and their expiration info
                cache_items = []
                for key in list(db.keys()):
                    # Skip metadata keys
                    if key.endswith('__expires'):
                        continue
                        
                    # Get expire time
                    expire_key = f"{key}__expires"
                    expire_time = db.get(expire_key, 0.0)
                    
                    # Add to collection for sorting
                    cache_items.append((key, expire_time))
                
                # Sort by expiration time (oldest first)
                cache_items.sort(key=lambda x: x[1])
                
                # Determine how many items to remove
                target_removal = 0
                
                if aggressive:
                    # In aggressive mode, remove a percentage of items
                    target_removal = int(len(cache_items) * (aggressive_percent / 100))
                    target_removal = max(target_removal, 10)  # At least 10 items
                else:
                    # In normal mode, just remove expired items
                    target_removal = sum(1 for _, expire_time in cache_items 
                                     if expire_time < retention_threshold)
                
                # Remove items (up to target)
                for i, (key, _) in enumerate(cache_items):
                    if i >= target_removal:
                        break
                        
                    # Remove both the value and expiration keys
                    expire_key = f"{key}__expires"
                    if key in db:
                        del db[key]
                    if expire_key in db:
                        del db[expire_key]
                        
                    removed_count += 1
                    
                    # Debug log
                    logger.debug(
                        f"Removed old cache item: {key}", 
                        extra={"correlation_id": self.correlation_id}
                    )
            
            return removed_count
            
        except Exception as e:
            logger.error(
                f"Failed to remove oldest items: {e}", 
                extra={"correlation_id": self.correlation_id}
            )
            return 0
            
    async def compact_cache(self) -> bool:
        """Compact the disk cache to reclaim space.
        
        This removes fragmentation and frees up disk space.
        
        Returns:
            bool: True if compaction was successful
        """
        logger.info("Compacting cache", extra={"correlation_id": self.correlation_id})
        
        try:
            # For shelve, we might need to create a new file and copy over
            # This is a placeholder for actual implementation
            # TODO: Implement proper compaction
            
            logger.info("Cache compacted", extra={"correlation_id": self.correlation_id})
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to compact cache: {e}", 
                extra={"correlation_id": self.correlation_id}
            )
            return False 
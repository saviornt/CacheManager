"""Disk-based cache layer implementation."""

import asyncio
import os
import shelve
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from threading import RLock

from ..core.exceptions import CacheStorageError
from ..core.circuit_breaker import CircuitBreaker
from .base_layer import BaseCacheLayer

logger = logging.getLogger(__name__)

class DiskLayer(BaseCacheLayer):
    """Disk-based cache layer implementation using Python's shelve.
    
    This layer stores cache data on disk for persistence across process restarts.
    """
    
    def __init__(self, namespace: str, ttl: int, cache_dir: str, cache_file: str,
                 retry_attempts: int = 3, retry_delay: int = 2):
        """Initialize the disk cache layer.
        
        Args:
            namespace: Namespace prefix for cache keys
            ttl: Default time-to-live in seconds for cached values
            cache_dir: Directory to store cache files
            cache_file: Name of the cache file
            retry_attempts: Number of retry attempts for disk operations
            retry_delay: Delay between retries in seconds
        """
        super().__init__(namespace, ttl)
        
        self.cache_dir = cache_dir
        self.cache_file = cache_file
        self.cache_path = os.path.join(cache_dir, cache_file)
        
        # Create cache directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)
        
        # For thread safety when updating metadata
        self._lock = RLock()
        
        # Metadata file to track expiry times
        self._metadata_path = f"{self.cache_path}_metadata"
        self._metadata: Dict[str, float] = {}
        self._load_metadata()
        
        # Circuit breakers for disk operations
        self._shelve_get_breaker = CircuitBreaker(
            failure_threshold=retry_attempts,
            reset_timeout=retry_delay * 10,
            operation_name="shelve_get"
        )
        
        self._shelve_set_breaker = CircuitBreaker(
            failure_threshold=retry_attempts,
            reset_timeout=retry_delay * 10,
            operation_name="shelve_set"
        )
    
    def _load_metadata(self) -> None:
        """Load metadata from disk if it exists."""
        try:
            # Create empty metadata if file doesn't exist
            if not os.path.exists(self._metadata_path):
                with open(self._metadata_path, 'wb') as f:
                    # Write empty dictionary
                    f.write(b'{}\n')
                self._metadata = {}
                return
                
            # Load existing metadata
            with shelve.open(self._metadata_path, flag='r') as shelf:
                # Copy all items to our in-memory metadata
                with self._lock:
                    self._metadata = dict(shelf)
                    
        except Exception as e:
            logger.error(f"Failed to load cache metadata: {e}", 
                        extra={'correlation_id': self._correlation_id})
            # If we can't load, use empty metadata
            self._metadata = {}
    
    def _save_metadata(self) -> None:
        """Save metadata to disk."""
        try:
            with shelve.open(self._metadata_path, flag='n') as shelf:
                # Save all items
                with self._lock:
                    for key, value in self._metadata.items():
                        shelf[key] = value
        except Exception as e:
            logger.error(f"Failed to save cache metadata: {e}", 
                        extra={'correlation_id': self._correlation_id})
    
    def _is_expired(self, key: str) -> bool:
        """Check if a key is expired based on metadata.
        
        Args:
            key: The cache key
            
        Returns:
            bool: True if the key is expired or not found
        """
        with self._lock:
            if key not in self._metadata:
                return True
                
            expiry_time = self._metadata[key]
            return time.time() > expiry_time
    
    def _clean_expired_keys(self) -> None:
        """Remove expired keys from metadata and optionally from the cache."""
        now = time.time()
        to_remove = []
        
        # Find expired keys
        with self._lock:
            for key, expiry_time in self._metadata.items():
                if now > expiry_time:
                    to_remove.append(key)
            
            # Remove from metadata
            for key in to_remove:
                del self._metadata[key]
        
        # Save updated metadata
        if to_remove:
            self._save_metadata()
            logger.debug(f"Removed {len(to_remove)} expired keys from disk cache metadata", 
                        extra={'correlation_id': self._correlation_id})
    
    async def get(self, key: str) -> Tuple[bool, Any]:
        """Get a value from the disk cache.
        
        Args:
            key: The cache key (already namespaced)
            
        Returns:
            Tuple[bool, Any]: (found, value) tuple
        """
        # Check if key is expired first, to avoid disk access
        if self._is_expired(key):
            return False, None
            
        try:
            @self._shelve_get_breaker
            async def _shelve_get(k: str):
                # Use thread pool for blocking IO
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, self._sync_get, k)
                
            value = await _shelve_get(key)
            if value is not None:
                return True, value
        except Exception as e:
            logger.error(f"Disk cache get error: {e}", 
                        extra={'correlation_id': self._correlation_id})
        
        return False, None
    
    def _sync_get(self, key: str) -> Any:
        """Synchronous implementation of get operation.
        
        Args:
            key: The cache key
            
        Returns:
            Any: The cached value or None if not found
        """
        try:
            # Check again if expired (could have changed while waiting)
            if self._is_expired(key):
                return None
                
            with shelve.open(self.cache_path, flag='r') as db:
                if key in db:
                    return db[key]
        except Exception as e:
            logger.error(f"Error reading from disk cache: {e}", 
                        extra={'correlation_id': self._correlation_id})
            raise CacheStorageError(f"Failed to read from disk cache: {e}")
            
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in the disk cache.
        
        Args:
            key: The cache key (already namespaced)
            value: The value to cache
            ttl: Time to live in seconds (defaults to layer ttl)
            
        Returns:
            bool: True if set successfully
        """
        try:
            expiry_seconds = ttl if ttl is not None else self.ttl
            expiry_time = time.time() + expiry_seconds
            
            @self._shelve_set_breaker
            async def _shelve_set(k: str, v: Any, t: float):
                # Use thread pool for blocking IO
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, self._sync_set, k, v, t)
            
            success = await _shelve_set(key, value, expiry_time)
            return success
            
        except Exception as e:
            logger.error(f"Disk cache set error: {e}", 
                        extra={'correlation_id': self._correlation_id})
            return False
    
    def _sync_set(self, key: str, value: Any, expiry_time: float) -> bool:
        """Synchronous implementation of set operation.
        
        Args:
            key: The cache key
            value: The value to cache
            expiry_time: The expiry timestamp
            
        Returns:
            bool: True if set successfully
        """
        try:
            # Set the value in the shelve
            with shelve.open(self.cache_path, flag='c') as db:
                db[key] = value
                
            # Update metadata
            with self._lock:
                self._metadata[key] = expiry_time
            
            self._save_metadata()
            return True
        except Exception as e:
            logger.error(f"Error writing to disk cache: {e}", 
                        extra={'correlation_id': self._correlation_id})
            raise CacheStorageError(f"Failed to write to disk cache: {e}")
            
        return False
    
    async def delete(self, key: str) -> bool:
        """Delete a value from the disk cache.
        
        Args:
            key: The cache key (already namespaced)
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            # Check if key exists in metadata
            with self._lock:
                exists = key in self._metadata
                if exists:
                    del self._metadata[key]
                    self._save_metadata()
            
            if not exists:
                return False
                
            # Delete from shelve
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._sync_delete, key)
            
        except Exception as e:
            logger.error(f"Disk cache delete error: {e}", 
                        extra={'correlation_id': self._correlation_id})
            return False
    
    def _sync_delete(self, key: str) -> bool:
        """Synchronous implementation of delete operation.
        
        Args:
            key: The cache key
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            with shelve.open(self.cache_path, flag='w') as db:
                if key in db:
                    del db[key]
                    return True
        except Exception as e:
            logger.error(f"Error deleting from disk cache: {e}", 
                        extra={'correlation_id': self._correlation_id})
            
        return False
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from the disk cache.
        
        Args:
            keys: List of cache keys (already namespaced)
            
        Returns:
            Dict[str, Any]: Dictionary mapping keys to their values
        """
        if not keys:
            return {}
            
        result = {}
        # Filter out expired keys
        valid_keys = [k for k in keys if not self._is_expired(k)]
        
        if not valid_keys:
            return {}
            
        try:
            @self._shelve_get_breaker
            async def _shelve_get_many(ks: List[str]) -> Dict[str, Any]:
                # Use thread pool for blocking IO
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, self._sync_get_many, ks)
                
            result = await _shelve_get_many(valid_keys)
            
        except Exception as e:
            logger.error(f"Disk cache get_many error: {e}", 
                        extra={'correlation_id': self._correlation_id})
        
        return result
    
    def _sync_get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Synchronous implementation of get_many operation.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dict[str, Any]: Dictionary mapping keys to their values
        """
        result = {}
        try:
            with shelve.open(self.cache_path, flag='r') as db:
                for key in keys:
                    if key in db:
                        result[key] = db[key]
        except Exception as e:
            logger.error(f"Error reading multiple keys from disk cache: {e}", 
                        extra={'correlation_id': self._correlation_id})
            raise CacheStorageError(f"Failed to read from disk cache: {e}")
            
        return result
    
    async def set_many(self, key_values: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values in the disk cache.
        
        Args:
            key_values: Dictionary mapping keys to values
            ttl: Time to live in seconds (defaults to layer ttl)
            
        Returns:
            bool: True if all values were set successfully
        """
        if not key_values:
            return True
            
        try:
            expiry_seconds = ttl if ttl is not None else self.ttl
            expiry_time = time.time() + expiry_seconds
            
            @self._shelve_set_breaker
            async def _shelve_set_many(kv_dict: Dict[str, Any], t: float):
                # Use thread pool for blocking IO
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, self._sync_set_many, kv_dict, t)
            
            success = await _shelve_set_many(key_values, expiry_time)
            return success
            
        except Exception as e:
            logger.error(f"Disk cache set_many error: {e}", 
                        extra={'correlation_id': self._correlation_id})
            return False
    
    def _sync_set_many(self, key_values: Dict[str, Any], expiry_time: float) -> bool:
        """Synchronous implementation of set_many operation.
        
        Args:
            key_values: Dictionary mapping keys to values
            expiry_time: The expiry timestamp
            
        Returns:
            bool: True if all values were set successfully
        """
        try:
            # Set the values in the shelve
            with shelve.open(self.cache_path, flag='c') as db:
                for key, value in key_values.items():
                    db[key] = value
                    
            # Update metadata
            with self._lock:
                for key in key_values.keys():
                    self._metadata[key] = expiry_time
            
            self._save_metadata()
            return True
        except Exception as e:
            logger.error(f"Error writing multiple keys to disk cache: {e}", 
                        extra={'correlation_id': self._correlation_id})
            raise CacheStorageError(f"Failed to write to disk cache: {e}")
            
        return False
    
    async def clear(self) -> bool:
        """Clear all values in the disk cache.
        
        Only clears keys with this instance's namespace.
        
        Returns:
            bool: True if cleared successfully
        """
        try:
            # Clear all metadata
            with self._lock:
                self._metadata.clear()
                self._save_metadata()
            
            # Delete and recreate the shelve file
            loop = asyncio.get_running_loop()
            success = await loop.run_in_executor(None, self._sync_clear)
            
            logger.info(f"Cleared disk cache at {self.cache_path}", 
                       extra={'correlation_id': self._correlation_id})
                       
            return success
        except Exception as e:
            logger.error(f"Error clearing disk cache: {e}", 
                        extra={'correlation_id': self._correlation_id})
            return False
    
    def _sync_clear(self) -> bool:
        """Synchronous implementation of clear operation.
        
        Returns:
            bool: True if cleared successfully
        """
        try:
            # Try to safely close and delete the shelve file
            db_extensions = [".bak", ".dat", ".dir"]
            
            for ext in db_extensions:
                path = f"{self.cache_path}{ext}"
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as e:
                        logger.warning(f"Failed to remove cache file {path}: {e}", 
                                      extra={'correlation_id': self._correlation_id})
            
            # Create a fresh empty shelve
            with shelve.open(self.cache_path, flag='n'):
                pass
                
            return True
        except Exception as e:
            logger.error(f"Error during disk cache clear: {e}", 
                        extra={'correlation_id': self._correlation_id})
            return False
    
    async def close(self) -> None:
        """Close the disk cache and save metadata.
        
        This should be called when the cache is no longer needed.
        """
        # Save metadata one final time
        self._save_metadata() 
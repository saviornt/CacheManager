"""In-memory cache layer implementation."""

import logging
from datetime import datetime, timedelta
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple
from collections import OrderedDict

from .base_layer import BaseCacheLayer
from ..cache_config import EvictionPolicy

logger = logging.getLogger(__name__)

class MemoryLayer(BaseCacheLayer):
    """In-memory cache layer implementation.
    
    This layer stores cache data in memory for fast access. Data is lost when the
    process exits.
    """
    
    def __init__(self, namespace: str, ttl: int, max_size: int = 1000, 
                 eviction_policy: EvictionPolicy = EvictionPolicy.LRU):
        """Initialize the memory cache layer.
        
        Args:
            namespace: Namespace prefix for cache keys
            ttl: Default time-to-live in seconds for cached values
            max_size: Maximum number of items to store in the cache
            eviction_policy: Policy for evicting items when cache is full
        """
        super().__init__(namespace, ttl)
        self.max_size = max_size
        self.eviction_policy = eviction_policy
        
        # Cache storage
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        
        # For eviction policy tracking
        self._keys_lock = RLock()
        
        # Use appropriate data structures based on eviction policy
        if self.eviction_policy == EvictionPolicy.LRU:
            # For LRU, we use OrderedDict to track access order
            self._cached_keys = OrderedDict()
        elif self.eviction_policy == EvictionPolicy.FIFO:
            # For FIFO, we use OrderedDict without reordering on access
            self._cached_keys = OrderedDict()
        elif self.eviction_policy == EvictionPolicy.LFU:
            # For LFU, we use OrderedDict for consistent iteration and Counter for frequencies
            from collections import Counter
            self._cached_keys = OrderedDict()
            self._access_frequencies = Counter()
    
    def _evict_if_needed(self) -> None:
        """Evict the least valuable cached key if the cache exceeds the maximum size.
        
        Uses a thread-safe approach to update the cache keys.
        The eviction strategy depends on the configured policy.
        """
        with self._keys_lock:
            if len(self._cached_keys) > self.max_size:
                # Remove keys until we're within limit
                evicted_keys = []
                
                while len(self._cached_keys) > self.max_size:
                    # Choose which key to evict based on the policy
                    if self.eviction_policy == EvictionPolicy.LRU:
                        # LRU - remove least recently used (first item in OrderedDict)
                        old_key, _ = self._cached_keys.popitem(last=False)
                    elif self.eviction_policy == EvictionPolicy.FIFO:
                        # FIFO - also remove first item (oldest added)
                        old_key, _ = self._cached_keys.popitem(last=False)
                    elif self.eviction_policy == EvictionPolicy.LFU:
                        # LFU - remove least frequently used
                        # Find key with minimum access frequency
                        if self._access_frequencies:
                            old_key = min(self._cached_keys.keys(), 
                                          key=lambda k: self._access_frequencies[k])
                            del self._cached_keys[old_key]
                            del self._access_frequencies[old_key]
                        else:
                            # Fallback if frequencies are somehow empty
                            old_key, _ = self._cached_keys.popitem(last=False)
                    
                    evicted_keys.append(old_key)
                    logger.debug(
                        f"Evicting key: {old_key} from memory cache using {self.eviction_policy} policy", 
                        extra={'correlation_id': self._correlation_id}
                    )
                
                # Remove the keys from the cache
                for key in evicted_keys:
                    if key in self._cache:
                        del self._cache[key]
                    if key in self._timestamps:
                        del self._timestamps[key]
    
    def _is_expired(self, key: str) -> bool:
        """Check if a key is expired.
        
        Args:
            key: The cache key
            
        Returns:
            bool: True if expired or doesn't exist, False otherwise
        """
        if key not in self._timestamps:
            return True
            
        timestamp = self._timestamps[key]
        return datetime.now() > timestamp

    def _clean_expired(self) -> None:
        """Remove expired items from the cache."""
        now = datetime.now()
        expired_keys = []
        
        for key, timestamp in self._timestamps.items():
            if now > timestamp:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_key(key)
    
    def _remove_key(self, key: str) -> None:
        """Remove a key from all internal data structures.
        
        Args:
            key: The cache key to remove
        """
        # Remove from main cache
        if key in self._cache:
            del self._cache[key]
        if key in self._timestamps:
            del self._timestamps[key]
            
        # Remove from eviction tracking
        with self._keys_lock:
            if key in self._cached_keys:
                del self._cached_keys[key]
            if self.eviction_policy == EvictionPolicy.LFU and key in self._access_frequencies:
                del self._access_frequencies[key]
    
    async def get(self, key: str) -> Tuple[bool, Any]:
        """Get a value from the memory cache.
        
        Args:
            key: The cache key
            
        Returns:
            Tuple[bool, Any]: (found, value) tuple
        """
        if key in self._cache:
            # Check expiration
            if not self._is_expired(key):
                # Update access tracking based on policy
                with self._keys_lock:
                    if self.eviction_policy == EvictionPolicy.LRU:
                        # Move to end of OrderedDict to mark as recently used
                        if key in self._cached_keys:
                            self._cached_keys.move_to_end(key)
                    elif self.eviction_policy == EvictionPolicy.LFU:
                        # Increment access frequency
                        self._access_frequencies[key] += 1
                
                return True, self._cache[key]
            else:
                # Expired, remove it
                self._remove_key(key)
        
        return False, None
        
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in the memory cache.
        
        Args:
            key: The cache key
            value: The value to cache
            ttl: Time to live in seconds (defaults to layer ttl)
            
        Returns:
            bool: True if set successfully
        """
        try:
            # Store the value
            self._cache[key] = value
            
            # Calculate expiry time
            expiry_seconds = ttl if ttl is not None else self.ttl
            self._timestamps[key] = datetime.now() + timedelta(seconds=expiry_seconds)
            
            # Update eviction tracking
            with self._keys_lock:
                self._cached_keys[key] = True
                
                # Handle different eviction policies
                if self.eviction_policy == EvictionPolicy.LRU:
                    # For LRU, move to end to mark as recently used
                    self._cached_keys.move_to_end(key)
                elif self.eviction_policy == EvictionPolicy.LFU:
                    # For LFU, initialize or increment access counter
                    self._access_frequencies[key] += 1
                
                # Check if we need to evict keys
                self._evict_if_needed()
            
            return True
        except Exception as e:
            logger.error(f"Memory layer set error: {e}", extra={'correlation_id': self._correlation_id})
            return False
            
    async def delete(self, key: str) -> bool:
        """Delete a value from the memory cache.
        
        Args:
            key: The cache key
            
        Returns:
            bool: True if deleted successfully
        """
        if key in self._cache:
            self._remove_key(key)
            return True
        return False
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from the memory cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dict[str, Any]: Dictionary mapping keys to their values
        """
        result = {}
        
        for key in keys:
            found, value = await self.get(key)
            if found:
                result[key] = value
        
        return result
    
    async def set_many(self, key_values: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values in the memory cache.
        
        Args:
            key_values: Dictionary mapping keys to values
            ttl: Time to live in seconds (defaults to layer ttl)
            
        Returns:
            bool: True if all values were set successfully
        """
        success = True
        
        for key, value in key_values.items():
            success = await self.set(key, value, ttl) and success
        
        return success
    
    async def clear(self) -> bool:
        """Clear all values in the memory cache.
        
        Returns:
            bool: True if cleared successfully
        """
        try:
            self._cache.clear()
            self._timestamps.clear()
            
            with self._keys_lock:
                self._cached_keys.clear()
                if self.eviction_policy == EvictionPolicy.LFU:
                    self._access_frequencies.clear()
            
            return True
        except Exception as e:
            logger.error(f"Error clearing memory cache: {e}", extra={'correlation_id': self._correlation_id})
            return False
    
    async def close(self) -> None:
        """Close the memory cache layer.
        
        For memory cache, this is a no-op as there are no connections to close.
        """
        pass 
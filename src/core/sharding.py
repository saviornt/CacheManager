"""Cache sharding for horizontal scaling of CacheManager.

This module provides functionality for distributing cache keys across multiple
cache nodes or instances, enabling horizontal scaling of the cache system.
"""

import hashlib
import logging
from typing import List, Dict, Any, Optional, Callable, TypeVar, Tuple

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ShardingStrategy:
    """Base class for cache sharding strategies."""
    
    def get_shard(self, key: str, num_shards: int) -> int:
        """Determine which shard a key belongs to.
        
        Args:
            key: The cache key
            num_shards: Total number of available shards
            
        Returns:
            int: Shard index (0 to num_shards-1)
        """
        raise NotImplementedError("Subclasses must implement get_shard")

class HashRingShardingStrategy(ShardingStrategy):
    """Consistent hashing implementation using a hash ring.
    
    This provides a more stable key distribution when adding or removing shards
    compared to simple modulo-based sharding. When the number of shards changes,
    only a fraction of keys need to be remapped.
    """
    
    def __init__(self, virtual_nodes: int = 100):
        """Initialize the consistent hashing ring.
        
        Args:
            virtual_nodes: Number of virtual nodes per physical shard
                Higher values give better distribution but use more memory
        """
        self._virtual_nodes = virtual_nodes
        self._ring: Dict[int, int] = {}  # Map from hash position to shard index
        self._sorted_keys: List[int] = []  # Sorted list of hash positions
    
    def initialize(self, num_shards: int) -> None:
        """Initialize the hash ring with the given number of shards.
        
        Args:
            num_shards: Number of physical shards
        """
        self._ring = {}
        
        # Add virtual nodes for each shard
        for shard_idx in range(num_shards):
            for vnode in range(self._virtual_nodes):
                # Create a hash key for this virtual node
                key = f"shard:{shard_idx}:vnode:{vnode}"
                hash_val = self._hash(key)
                
                # Map this hash to the physical shard
                self._ring[hash_val] = shard_idx
        
        # Sort the hash keys for binary search
        self._sorted_keys = sorted(self._ring.keys())
    
    def _hash(self, key: str) -> int:
        """Hash a key to a position on the ring.
        
        Args:
            key: String to hash
            
        Returns:
            int: Hash value
        """
        return int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16)
    
    def get_shard(self, key: str, num_shards: int) -> int:
        """Get the shard index for a key using consistent hashing.
        
        Args:
            key: The cache key
            num_shards: Total number of shards
            
        Returns:
            int: Shard index
        """
        # Initialize if not already done or if number of shards changed
        if not self._ring or len(set(self._ring.values())) != num_shards:
            self.initialize(num_shards)
        
        # If no virtual nodes, fallback to modulo hashing
        if not self._sorted_keys:
            return self._hash(key) % num_shards
        
        # Find the nearest point on the ring
        hash_val = self._hash(key)
        
        # Binary search for the first position >= hash_val
        pos = self._binary_search(hash_val)
        
        # If we went past the end, wrap around to the first position
        if pos >= len(self._sorted_keys):
            pos = 0
            
        # Return the shard corresponding to this position
        return self._ring[self._sorted_keys[pos]]
    
    def _binary_search(self, hash_val: int) -> int:
        """Find the index of the first key greater than or equal to hash_val.
        
        Args:
            hash_val: Hash value to search for
            
        Returns:
            int: Index in sorted_keys
        """
        left, right = 0, len(self._sorted_keys) - 1
        
        while left <= right:
            mid = (left + right) // 2
            if self._sorted_keys[mid] < hash_val:
                left = mid + 1
            else:
                right = mid - 1
                
        return left if left < len(self._sorted_keys) else 0

class ModuloShardingStrategy(ShardingStrategy):
    """Simple modulo-based sharding strategy.
    
    This distributes keys evenly but is not stable when the number of
    shards changes.
    """
    
    def get_shard(self, key: str, num_shards: int) -> int:
        """Get the shard index using simple modulo hashing.
        
        Args:
            key: The cache key
            num_shards: Total number of shards
            
        Returns:
            int: Shard index
        """
        hash_val = int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16)
        return hash_val % num_shards

def get_routing_key(key: str, namespace: Optional[str] = None) -> str:
    """Generate a routing key for sharding that includes the namespace.
    
    Args:
        key: The cache key
        namespace: Optional namespace
        
    Returns:
        str: Routing key for sharding
    """
    if namespace:
        return f"{namespace}:{key}"
    return key

class ShardManager:
    """Manages mapping of keys to shards for distributed caching.
    
    This class handles routing cache operations to the appropriate shard
    based on the key.
    """
    
    def __init__(
        self,
        num_shards: int = 1,
        strategy: ShardingStrategy = None,
        shard_resolver: Optional[Callable[[int], Any]] = None
    ):
        """Initialize the shard manager.
        
        Args:
            num_shards: Number of cache shards
            strategy: Sharding strategy to use (defaults to HashRingShardingStrategy)
            shard_resolver: Function to resolve a shard index to the actual shard
                implementation (e.g., a CacheManager instance or Redis connection)
        """
        self._num_shards = num_shards
        self._strategy = strategy or HashRingShardingStrategy()
        self._shard_resolver = shard_resolver
    
    def get_shard_for_key(self, key: str, namespace: Optional[str] = None) -> Tuple[int, Any]:
        """Get the shard for a given key.
        
        Args:
            key: The cache key
            namespace: Optional namespace
            
        Returns:
            Tuple containing:
                - int: Shard index
                - Any: Shard implementation if resolver is provided, else None
        """
        routing_key = get_routing_key(key, namespace)
        shard_idx = self._strategy.get_shard(routing_key, self._num_shards)
        
        if self._shard_resolver:
            return shard_idx, self._shard_resolver(shard_idx)
        return shard_idx, None
    
    def get_shard_indices_for_keys(self, keys: List[str], namespace: Optional[str] = None) -> Dict[int, List[str]]:
        """Group keys by their shard indices.
        
        This is useful for batch operations to route keys to their appropriate shards.
        
        Args:
            keys: List of cache keys
            namespace: Optional namespace
            
        Returns:
            Dict mapping shard indices to lists of keys belonging to that shard
        """
        shard_to_keys: Dict[int, List[str]] = {}
        
        for key in keys:
            routing_key = get_routing_key(key, namespace)
            shard_idx = self._strategy.get_shard(routing_key, self._num_shards)
            
            if shard_idx not in shard_to_keys:
                shard_to_keys[shard_idx] = []
            shard_to_keys[shard_idx].append(key)
            
        return shard_to_keys
    
    def update_shard_count(self, num_shards: int) -> None:
        """Update the number of shards.
        
        This may cause keys to be remapped to different shards,
        depending on the sharding strategy.
        
        Args:
            num_shards: New number of shards
        """
        if num_shards <= 0:
            raise ValueError("Number of shards must be positive")
            
        if isinstance(self._strategy, HashRingShardingStrategy):
            self._strategy.initialize(num_shards)
            
        self._num_shards = num_shards
        logger.info(f"Updated shard count to {num_shards}")
    
    @property
    def num_shards(self) -> int:
        """Get the current number of shards.
        
        Returns:
            int: Number of shards
        """
        return self._num_shards 
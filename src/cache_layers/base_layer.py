"""Base abstract class for cache layers implementation."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, TypeVar

T = TypeVar('T')

logger = logging.getLogger(__name__)

class BaseCacheLayer(ABC):
    """Abstract base class that defines the interface for all cache layers.
    
    All cache layer implementations must extend this class and implement
    the required methods.
    """
    
    def __init__(self, namespace: str, ttl: int):
        """Initialize the cache layer.
        
        Args:
            namespace: Namespace prefix for cache keys
            ttl: Default time-to-live in seconds for cached values
        """
        self.namespace = namespace
        self.ttl = ttl
        self._correlation_id = f"L-{namespace[:4]}"
        
    def _namespace_key(self, key: str) -> str:
        """Add namespace prefix to a key.
        
        Args:
            key: The original key
            
        Returns:
            str: The namespaced key
        """
        if self.namespace == "default":
            return key
        return f"{self.namespace}:{key}"
    
    def _remove_namespace(self, namespaced_key: str) -> str:
        """Remove namespace prefix from a key.
        
        Args:
            namespaced_key: The namespaced key
            
        Returns:
            str: The original key without namespace
        """
        if self.namespace == "default" or ":" not in namespaced_key:
            return namespaced_key
        _, key = namespaced_key.split(":", 1)
        return key
    
    @abstractmethod
    async def get(self, key: str) -> Tuple[bool, Any]:
        """Get a value from the cache layer.
        
        Args:
            key: The cache key (already namespaced)
            
        Returns:
            Tuple[bool, Any]: (found, value) tuple
        """
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in the cache layer.
        
        Args:
            key: The cache key (already namespaced)
            value: The value to cache
            ttl: Time to live in seconds (defaults to layer ttl)
            
        Returns:
            bool: True if set successfully
        """
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a value from the cache layer.
        
        Args:
            key: The cache key (already namespaced)
            
        Returns:
            bool: True if deleted successfully
        """
        pass
    
    @abstractmethod
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from the cache layer.
        
        Args:
            keys: List of cache keys (already namespaced)
            
        Returns:
            Dict[str, Any]: Dictionary mapping keys to their values
        """
        pass
    
    @abstractmethod
    async def set_many(self, key_values: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values in the cache layer.
        
        Args:
            key_values: Dictionary mapping keys to values
            ttl: Time to live in seconds (defaults to layer ttl)
            
        Returns:
            bool: True if all values were set successfully
        """
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """Clear all values in this cache layer.
        
        Returns:
            bool: True if cleared successfully
        """
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Close connections and release resources.
        
        Should be called when the cache layer is no longer needed.
        """
        pass 
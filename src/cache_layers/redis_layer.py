"""Redis cache layer implementation."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..core.exceptions import CacheSerializationError
from ..core.circuit_breaker import CircuitBreaker
from ..utils.serialization import serialize, deserialize
from .base_layer import BaseCacheLayer

logger = logging.getLogger(__name__)

# Try to import the async redis client
try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    redis = None
    HAS_REDIS = False
    logger.warning("redis-py not installed or doesn't have async support",
                  extra={'correlation_id': 'INIT'})

class RedisLayer(BaseCacheLayer):
    """Redis cache layer implementation.
    
    This layer stores cache data in a Redis server for shared access across
    multiple processes or machines.
    """
    
    def __init__(self, namespace: str, ttl: int, redis_url: str, 
                 retry_attempts: int = 3, retry_delay: int = 2,
                 enable_compression: bool = False,
                 compression_min_size: int = 1024,
                 compression_level: int = 6):
        """Initialize the Redis cache layer.
        
        Args:
            namespace: Namespace prefix for cache keys
            ttl: Default time-to-live in seconds for cached values
            redis_url: URL for connecting to Redis server
            retry_attempts: Number of retry attempts for Redis operations
            retry_delay: Delay between retries in seconds
            enable_compression: Whether to enable compression
            compression_min_size: Minimum size for compression to be applied
            compression_level: Compression level (1-9) for zlib
        """
        super().__init__(namespace, ttl)
        
        if not HAS_REDIS:
            raise ImportError("Redis support requires redis-py with async support. "
                              "Install with 'pip install redis[hiredis]'")
            
        self.redis_url = redis_url
        self.enable_compression = enable_compression
        self.compression_min_size = compression_min_size
        self.compression_level = compression_level
        
        # Redis client instances
        self._redis_client = None
        self._connection_pool = None
        
        # Circuit breakers for Redis operations
        self._redis_get_breaker = CircuitBreaker(
            failure_threshold=retry_attempts * 2,
            reset_timeout=retry_delay * 5,
            operation_name="redis_get"
        )
        
        self._redis_set_breaker = CircuitBreaker(
            failure_threshold=retry_attempts * 2,
            reset_timeout=retry_delay * 5,
            operation_name="redis_set"
        )
    
    def _get_redis_client(self):
        """Get or create a Redis client using connection pooling.
        
        Returns:
            redis.Redis: Redis client instance
        """
        if self._redis_client is None:
            logger.debug("Creating new Redis client with connection pool", 
                        extra={'correlation_id': self._correlation_id})
            # Create and use a connection pool
            if self._connection_pool is None:
                self._connection_pool = redis.ConnectionPool.from_url(self.redis_url)
                logger.debug(f"Created Redis connection pool to {self.redis_url}", 
                            extra={'correlation_id': self._correlation_id})
            self._redis_client = redis.Redis(connection_pool=self._connection_pool)
        return self._redis_client
    
    async def get(self, key: str) -> Tuple[bool, Any]:
        """Get a value from the Redis cache.
        
        Args:
            key: The cache key
            
        Returns:
            Tuple[bool, Any]: (found, value) tuple
        """
        try:
            redis_client = self._get_redis_client()
            if not redis_client:
                logger.warning("Redis client unavailable", 
                              extra={'correlation_id': self._correlation_id})
                return False, None
                
            @self._redis_get_breaker
            async def _redis_get(k: str):
                return await redis_client.get(k)
            
            data = await _redis_get(key)
            if data:
                try:
                    value = deserialize(data)
                    return True, value
                except CacheSerializationError as e:
                    logger.error(f"Error deserializing Redis data: {e}", 
                                extra={'correlation_id': self._correlation_id})
                    return False, None
        except Exception as e:
            logger.error(f"Redis get error: {e}", 
                        extra={'correlation_id': self._correlation_id})
            return False, None
        
        return False, None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in the Redis cache.
        
        Args:
            key: The cache key
            value: The value to cache
            ttl: Time to live in seconds (defaults to layer ttl)
            
        Returns:
            bool: True if set successfully
        """
        try:
            redis_client = self._get_redis_client()
            if not redis_client:
                logger.warning("Redis client unavailable", 
                              extra={'correlation_id': self._correlation_id})
                return False
                
            # Serialize the value before storing
            try:
                serialized_value = serialize(
                    value, 
                    self.enable_compression, 
                    self.compression_min_size, 
                    self.compression_level
                )
            except CacheSerializationError as e:
                logger.error(f"Error serializing value: {e}", 
                            extra={'correlation_id': self._correlation_id})
                return False
            
            expiry = ttl if ttl is not None else self.ttl
            
            @self._redis_set_breaker
            async def _redis_set(k: str, v: bytes, ex: int):
                return await redis_client.set(k, v, ex=ex)
                
            result = await _redis_set(key, serialized_value, expiry)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis set error: {e}", 
                        extra={'correlation_id': self._correlation_id})
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a value from the Redis cache.
        
        Args:
            key: The cache key
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            redis_client = self._get_redis_client()
            if not redis_client:
                logger.warning("Redis client unavailable", 
                              extra={'correlation_id': self._correlation_id})
                return False
                
            result = await redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}", 
                        extra={'correlation_id': self._correlation_id})
            return False
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from the Redis cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dict[str, Any]: Dictionary mapping keys to their values
        """
        if not keys:
            return {}
            
        try:
            redis_client = self._get_redis_client()
            if not redis_client:
                logger.warning("Redis client unavailable", 
                              extra={'correlation_id': self._correlation_id})
                return {}
                
            @self._redis_get_breaker
            async def _redis_mget(ks: List[str]):
                return await redis_client.mget(*ks)
                
            values = await _redis_mget(keys)
            
            # Process results
            result = {}
            for i, value in enumerate(values):
                if value is not None:
                    try:
                        key = keys[i]
                        deserialized = deserialize(value)
                        result[key] = deserialized
                    except Exception as e:
                        logger.error(f"Error deserializing value for key {keys[i]}: {e}", 
                                   extra={'correlation_id': self._correlation_id})
                        continue
                        
            return result
        except Exception as e:
            logger.error(f"Redis mget error: {e}", 
                        extra={'correlation_id': self._correlation_id})
            return {}
    
    async def set_many(self, key_values: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """Set multiple values in the Redis cache.
        
        Args:
            key_values: Dictionary mapping keys to values
            ttl: Time to live in seconds (defaults to layer ttl)
            
        Returns:
            bool: True if all values were set successfully
        """
        if not key_values:
            return True
            
        try:
            redis_client = self._get_redis_client()
            if not redis_client:
                logger.warning("Redis client unavailable", 
                              extra={'correlation_id': self._correlation_id})
                return False
            
            # Serialize all values before storing
            try:
                serialized_dict = {}
                for key, value in key_values.items():
                    try:
                        serialized_dict[key] = serialize(
                            value, 
                            self.enable_compression, 
                            self.compression_min_size, 
                            self.compression_level
                        )
                    except Exception as e:
                        logger.error(f"Error serializing value for key '{key}': {e}", 
                                    extra={'correlation_id': self._correlation_id})
                        # Skip this key and continue with others
                        continue
                
                if not serialized_dict:
                    return False
                
                @self._redis_set_breaker
                async def _redis_pipeline_set(kv_dict: Dict[str, bytes], ex: int):
                    """Set multiple keys using a Redis pipeline for efficiency."""
                    pipe = redis_client.pipeline()
                    for k, v in kv_dict.items():
                        pipe.set(k, v, ex=ex)
                    return await pipe.execute()
                
                expiry = ttl if ttl is not None else self.ttl
                results = await _redis_pipeline_set(serialized_dict, expiry)
                
                # Check if all operations succeeded
                return all(bool(result) for result in results)
            except Exception as e:
                logger.error(f"Redis set_many error: {e}", 
                           extra={'correlation_id': self._correlation_id})
                return False
        except Exception as e:
            logger.error(f"Redis set_many outer error: {e}", 
                        extra={'correlation_id': self._correlation_id})
            return False
    
    async def clear(self) -> bool:
        """Clear all values in this Redis cache.
        
        Only clears keys with this instance's namespace.
        
        Returns:
            bool: True if cleared successfully
        """
        try:
            redis_client = self._get_redis_client()
            if not redis_client:
                logger.warning("Redis client unavailable", 
                              extra={'correlation_id': self._correlation_id})
                return False
                
            # Only clear keys used by this instance with namespace
            if self.namespace != "default":
                pattern = f"{self.namespace}:*"
                # Scan for keys with this pattern
                cursor = 0
                deleted_count = 0
                
                while True:
                    cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
                    if keys:
                        await redis_client.delete(*keys)
                        deleted_count += len(keys)
                    if cursor == 0:
                        break
                
                logger.info(f"Cleared {deleted_count} keys with pattern {pattern}", 
                           extra={'correlation_id': self._correlation_id})
                return True
            else:
                # If no namespace, don't delete anything in Redis
                # to avoid clearing other data
                logger.warning(
                    "Not clearing Redis cache with default namespace to avoid data loss. "
                    "Use a specific namespace if you want to clear Redis cache.",
                    extra={'correlation_id': self._correlation_id}
                )
                return False
        except Exception as e:
            logger.error(f"Error clearing Redis cache: {e}", 
                        extra={'correlation_id': self._correlation_id})
            return False
    
    async def close(self) -> None:
        """Close the Redis client and release resources."""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
        
        if self._connection_pool:
            self._connection_pool.disconnect()
            self._connection_pool = None 
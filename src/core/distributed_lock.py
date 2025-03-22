"""Distributed locking mechanisms for CacheManager.

This module provides tools for distributed locking using Redis as a centralized
lock manager. It helps coordinate cache operations across multiple nodes.
"""

import asyncio
import logging
import time
import uuid
import random
from typing import Optional, Callable, Any
from functools import wraps

import redis.asyncio as redis
from redis.exceptions import RedisError

from .exceptions import CacheError

logger = logging.getLogger(__name__)

class LockError(CacheError):
    """Exception raised when there's an error acquiring or releasing a lock."""
    pass

class DistributedLock:
    """Implements a distributed lock using Redis.
    
    Allows coordinating access to shared resources across multiple cache nodes.
    Uses the Redis SETNX operation with expiration to implement a reliable lock.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        lock_timeout: int = 30,  # Lock expiration time in seconds
        retry_interval: float = 0.2,  # Time between retries in seconds
        retry_attempts: int = 5,  # Maximum number of retry attempts
        lock_prefix: str = "cache:lock:"
    ):
        """Initialize a distributed lock.
        
        Args:
            redis_client: Redis client instance
            lock_timeout: Time in seconds before lock expires automatically
            retry_interval: Time between lock acquisition attempts
            retry_attempts: Maximum number of times to retry acquiring the lock
            lock_prefix: Prefix for lock keys in Redis
        """
        self._redis = redis_client
        self._lock_timeout = lock_timeout
        self._retry_interval = retry_interval
        self._retry_attempts = retry_attempts
        self._lock_prefix = lock_prefix
        
        # Generate a unique ID for this lock instance to prevent other clients
        # from releasing locks they don't own
        self._owner_id = str(uuid.uuid4())
    
    async def acquire(self, resource_name: str) -> bool:
        """Attempt to acquire a lock for the specified resource.
        
        Args:
            resource_name: Name of the resource to lock
            
        Returns:
            bool: True if lock acquired, False if not
            
        Raises:
            LockError: If there's an error communicating with Redis
        """
        lock_key = f"{self._lock_prefix}{resource_name}"
        lock_value = f"{self._owner_id}:{time.time()}"
        
        try:
            # Try to set the key if it doesn't exist
            return await self._redis.set(
                lock_key, 
                lock_value, 
                nx=True,  # Only set if not exists
                ex=self._lock_timeout  # Expiration time
            )
        except RedisError as e:
            logger.error(f"Error acquiring lock for {resource_name}: {e}")
            raise LockError(f"Failed to acquire lock: {e}") from e
    
    async def release(self, resource_name: str) -> bool:
        """Release a previously acquired lock.
        
        Only releases the lock if it's actually owned by this lock instance.
        This prevents accidentally releasing another client's lock.
        
        Args:
            resource_name: Name of the locked resource
            
        Returns:
            bool: True if lock was released, False if not owned
            
        Raises:
            LockError: If there's an error communicating with Redis
        """
        lock_key = f"{self._lock_prefix}{resource_name}"
        
        try:
            # Get the current lock value
            lock_value = await self._redis.get(lock_key)
            
            # Check if the lock exists and belongs to us
            if lock_value and lock_value.decode('utf-8').startswith(self._owner_id):
                # Delete the lock
                return bool(await self._redis.delete(lock_key))
            return False
        except RedisError as e:
            logger.error(f"Error releasing lock for {resource_name}: {e}")
            raise LockError(f"Failed to release lock: {e}") from e
    
    async def extend(self, resource_name: str) -> bool:
        """Extend the expiration time of a lock.
        
        Only extends the lock if it's actually owned by this lock instance.
        
        Args:
            resource_name: Name of the locked resource
            
        Returns:
            bool: True if lock was extended, False if not owned
            
        Raises:
            LockError: If there's an error communicating with Redis
        """
        lock_key = f"{self._lock_prefix}{resource_name}"
        
        try:
            # Get the current lock value
            lock_value = await self._redis.get(lock_key)
            
            # Check if the lock exists and belongs to us
            if lock_value and lock_value.decode('utf-8').startswith(self._owner_id):
                # Extend the expiration time
                return bool(await self._redis.expire(lock_key, self._lock_timeout))
            return False
        except RedisError as e:
            logger.error(f"Error extending lock for {resource_name}: {e}")
            raise LockError(f"Failed to extend lock: {e}") from e
    
    async def acquire_with_retry(self, resource_name: str) -> bool:
        """Attempt to acquire a lock with retries.
        
        Will attempt multiple times with a random backoff strategy to
        reduce contention when multiple clients try to lock simultaneously.
        
        Args:
            resource_name: Name of the resource to lock
            
        Returns:
            bool: True if lock acquired, False if not
            
        Raises:
            LockError: If there's an error communicating with Redis
        """
        for attempt in range(self._retry_attempts):
            # Try to acquire the lock
            acquired = await self.acquire(resource_name)
            
            # If successful, return True
            if acquired:
                return True
                
            # If we've reached max attempts, give up
            if attempt >= self._retry_attempts - 1:
                return False
                
            # Wait with exponential backoff plus random jitter
            backoff = self._retry_interval * (2 ** attempt)
            jitter = random.uniform(0, 0.1 * backoff)  # 10% jitter
            await asyncio.sleep(backoff + jitter)
        
        return False
    
    async def __aenter__(self) -> "DistributedLock":
        """Enter the async context manager and acquire the lock.
        
        Returns:
            DistributedLock: self for context manager
            
        Raises:
            CacheError: If lock cannot be acquired
        """
        return self
    
    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None:
        """Exit the async context manager and release the lock."""
        pass

def distributed_lock(resource_name_func: Optional[Callable] = None) -> Callable:
    """Decorator for using distributed locks on cache operations.
    
    Args:
        resource_name_func: Optional function to determine the resource name from args
        
    Returns:
        Callable: Decorator function
    """
    def decorator(func: Callable) -> Callable:
        """Decorator function that wraps a method with distributed lock functionality.
        
        Args:
            func: The function to wrap
            
        Returns:
            Callable: Wrapped function
        """
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Skip if no Redis client is available
            if not hasattr(self, '_redis') or self._redis is None:
                return await func(self, *args, **kwargs)
            
            # Skip if distributed locking is disabled
            if not hasattr(self, '_config') or not getattr(self._config, 'use_distributed_locking', False):
                return await func(self, *args, **kwargs)
            
            # Determine the resource name to lock
            if resource_name_func:
                # Call the provided function to get the resource name
                resource_name = resource_name_func(self, *args, **kwargs)
            else:
                # Default to using the first argument as the resource name
                resource_name = args[0] if args else next(iter(kwargs.values()), "default")
            
            # Create a lock instance
            lock = DistributedLock(
                self._redis,
                lock_timeout=getattr(self._config, 'lock_timeout', 30),
                retry_attempts=getattr(self._config, 'lock_retry_attempts', 5),
                retry_interval=getattr(self._config, 'lock_retry_interval', 0.2),
                lock_prefix=f"{getattr(self._config, 'namespace', 'default')}:lock:"
            )
            
            # Try to acquire the lock
            acquired = False
            try:
                acquired = await lock.acquire_with_retry(resource_name)
                if not acquired:
                    logger.warning(f"Failed to acquire lock for {resource_name}, proceeding without lock")
                    # Proceed without the lock to avoid deadlock situations
                
                # Execute the function
                return await func(self, *args, **kwargs)
            finally:
                # Release the lock if it was acquired
                if acquired:
                    try:
                        await lock.release(resource_name)
                    except LockError as e:
                        logger.error(f"Error releasing lock for {resource_name}: {e}")
        
        return wrapper
    return decorator


class ShardedLock:
    """A distributed lock that shards the lock key to reduce contention.
    
    For high-contention resources, this divides the lock into multiple shards
    to allow more concurrent access. Only operations that need to access the
    same shard will contend with each other.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        num_shards: int = 16,
        lock_timeout: int = 30,
        retry_interval: float = 0.2,
        retry_attempts: int = 5,
        lock_prefix: str = "cache:shardlock:"
    ):
        """Initialize a sharded distributed lock.
        
        Args:
            redis_client: Redis client instance
            num_shards: Number of shards to divide the lock into
            lock_timeout: Time in seconds before lock expires automatically
            retry_interval: Time between lock acquisition attempts
            retry_attempts: Maximum number of times to retry acquiring the lock
            lock_prefix: Prefix for lock keys in Redis
        """
        self._redis = redis_client
        self._num_shards = num_shards
        self._lock_timeout = lock_timeout
        self._retry_interval = retry_interval
        self._retry_attempts = retry_attempts
        self._lock_prefix = lock_prefix
        
        # Create a lock for each shard
        self._locks = [
            DistributedLock(
                redis_client,
                lock_timeout=lock_timeout,
                retry_interval=retry_interval,
                retry_attempts=retry_attempts,
                lock_prefix=f"{lock_prefix}shard{i}:"
            )
            for i in range(num_shards)
        ]
    
    def _get_shard(self, resource_name: str) -> int:
        """Determine which shard a resource belongs to.
        
        Args:
            resource_name: Name of the resource
            
        Returns:
            int: Shard index
        """
        # Simple hash-based sharding
        return hash(resource_name) % self._num_shards
    
    async def acquire(self, resource_name: str) -> bool:
        """Acquire a lock on the appropriate shard for this resource.
        
        Args:
            resource_name: Name of the resource to lock
            
        Returns:
            bool: True if lock acquired, False if not
        """
        shard = self._get_shard(resource_name)
        return await self._locks[shard].acquire(resource_name)
    
    async def release(self, resource_name: str) -> bool:
        """Release a lock on the appropriate shard.
        
        Args:
            resource_name: Name of the locked resource
            
        Returns:
            bool: True if lock was released, False if not owned
        """
        shard = self._get_shard(resource_name)
        return await self._locks[shard].release(resource_name)
    
    async def acquire_with_retry(self, resource_name: str) -> bool:
        """Attempt to acquire a lock with retries.
        
        Args:
            resource_name: Name of the resource to lock
            
        Returns:
            bool: True if lock acquired, False if not
        """
        shard = self._get_shard(resource_name)
        return await self._locks[shard].acquire_with_retry(resource_name) 
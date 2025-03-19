import os
import shelve
import pickle
import time
import logging
from typing import Any, Optional
from collections import OrderedDict
from .cache_config import CacheConfig
from tenacity import retry, stop_after_attempt, wait_fixed

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import the async redis client
try:
    import redis.asyncio as redis
except ImportError:
    redis = None

class CacheManager:
    def __init__(self, config: CacheConfig = CacheConfig()):
        self.config = config
        self._use_redis = self.config.use_redis and redis is not None

        # Ensure the cache directory exists for shelve
        if not os.path.exists(self.config.cache_dir):
            os.makedirs(self.config.cache_dir)
        self.shelve_file = os.path.join(self.config.cache_dir, self.config.cache_file)
        
        # Use an OrderedDict to track cached keys for LRU eviction
        self.cached_keys = OrderedDict()

        # Redis client is lazily initialized
        self._redis_client = None

    def _get_redis_client(self):
        if self._redis_client is None and self._use_redis:
            # from_url creates a connection pool by default.
            self._redis_client = redis.from_url(self.config.full_redis_url)
        return self._redis_client

    def _evict_if_needed(self):
        """
        Evict the oldest cached key if the cache exceeds the maximum size.
        """
        if len(self.cached_keys) > self.config.cache_max_size:
            # Remove the oldest key(s) until within limit
            while len(self.cached_keys) > self.config.cache_max_size:
                old_key, _ = self.cached_keys.popitem(last=False)
                logger.info(f"Evicting key: {old_key} from cache (shelve)")
                with shelve.open(self.shelve_file, writeback=True) as db:
                    if old_key in db:
                        del db[old_key]

    @retry(stop=stop_after_attempt(CacheConfig().retry_attempts), 
           wait=wait_fixed(CacheConfig().retry_delay))
    async def get(self, key: str) -> Optional[Any]:
        start_time = time.time()
        try:
            if self._use_redis:
                client = self._get_redis_client()
                val = await client.get(key)
                if val is not None:
                    value = pickle.loads(val)
                else:
                    value = None
            else:
                with shelve.open(self.shelve_file) as db:
                    value = db.get(key)
            logger.info(f"GET key='{key}' completed in {time.time() - start_time:.4f} seconds")
            return value
        except Exception as e:
            logger.error(f"Error during GET for key '{key}': {e}")
            raise

    @retry(stop=stop_after_attempt(CacheConfig().retry_attempts), 
           wait=wait_fixed(CacheConfig().retry_delay))
    async def set(self, key: str, value: Any, expiration: Optional[int] = None):
        start_time = time.time()
        expiration = expiration or int(self.config.cache_ttl)
        try:
            # Track key usage with LRU (newest keys are appended)
            self.cached_keys.pop(key, None)
            self.cached_keys[key] = time.time()
            self._evict_if_needed()

            if self._use_redis:
                client = self._get_redis_client()
                # Serialize the data using pickle
                serialized_value = pickle.dumps(value)
                await client.set(key, serialized_value, ex=expiration)
            else:
                with shelve.open(self.shelve_file, writeback=True) as db:
                    db[key] = value
            logger.info(f"SET key='{key}' completed in {time.time() - start_time:.4f} seconds")
        except Exception as e:
            logger.error(f"Error during SET for key '{key}': {e}")
            raise

    async def clear(self):
        """Clear all cached keys relevant to this run."""
        try:
            if self._use_redis:
                client = self._get_redis_client()
                if self.cached_keys:
                    await client.delete(*list(self.cached_keys.keys()))
            else:
                with shelve.open(self.shelve_file, writeback=True) as db:
                    for key in list(self.cached_keys.keys()):
                        if key in db:
                            del db[key]
            self.cached_keys.clear()
            logger.info("Cache cleared successfully.")
        except Exception as e:
            logger.error(f"Error during CLEAR: {e}")
            raise

    async def close(self):
        """Cleanly close the redis connection if in use."""
        try:
            if self._use_redis and self._redis_client:
                await self._redis_client.close()
                logger.info("Redis client closed successfully.")
        except Exception as e:
            logger.error(f"Error during closing redis client: {e}")
            raise

    # Async context management to ensure proper cleanup
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

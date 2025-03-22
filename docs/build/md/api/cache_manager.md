# Cache Manager

The core caching system module that provides caching operations with support for multiple backends.

<a id="module-src.cache_manager"></a>

### *class* src.cache_manager.CacheManager(config=CacheConfig(cache_dir='.cache', cache_file='cache.db', cache_max_size=5000, cache_ttl=300.0, eviction_policy=<EvictionPolicy.LRU: 'lru'>, namespace='default', use_redis=False, redis_url='redis://localhost', redis_port=6379, redis_username='', redis_password='', memory_cache_ttl=60, memory_cache_enabled=True, use_layered_cache=False, cache_layers=[], write_through=True, read_through=True, enable_compression=True, compression_min_size=1024, compression_level=6, disk_usage_monitoring=True, disk_usage_threshold=75.0, disk_critical_threshold=90.0, disk_check_interval=3600, disk_retention_days=30, retry_attempts=3, retry_delay=2, environment=<Environment.DEV: 'dev'>, log_level=<LogLevel.DEBUG: 'debug'>, log_dir='./logs', log_to_file=False, log_max_size=10485760, log_backup_count=5, enable_telemetry=False, telemetry_interval=60, metrics_collection=True, enable_warmup=False, warmup_keys_file=None, warmup_on_start=False, enable_adaptive_ttl=False, adaptive_ttl_min=60, adaptive_ttl_max=86400, access_count_threshold=10, adaptive_ttl_adjustment_factor=1.5, use_distributed_locking=False, lock_timeout=30, lock_retry_attempts=5, lock_retry_interval=0.2, enable_sharding=False, num_shards=1, sharding_algorithm='consistent_hash', enable_invalidation=False, invalidation_channel='cache:invalidation', enable_encryption=False, encryption_key=None, encryption_salt=None, enable_data_signing=False, signing_key=None, signing_algorithm='sha256', enable_access_control=False, redis_ssl=False, redis_ssl_cert_reqs=None, redis_ssl_ca_certs=None, redis_connection_timeout=5.0, redis_max_connections=10, use_redis_sentinel=False, sentinel_master_name='mymaster', sentinel_addresses=[], disk_cache_enabled=True, disk_cache_ttl=3600.0))

Bases: `object`

Manages caching operations with support for multiple backends.

Features:
- Multiple backend support (in-memory, Redis, shelve)
- TTL (Time-To-Live) for cached items
- Serialization via msgpack (falls back to pickle)
- Thread-safe eviction policies (LRU, FIFO, LFU)
- Namespacing to prevent key collisions
- Circuit breaker pattern to handle backend failures
- In-memory caching layer for performance
- Layered cache approach with read-through/write-through
- Bulk operations (get_many, set_many)
- Function decorator for easy caching
- Compression support for large values

Initialize the cache manager with the given configuration.

* **Parameters:**
  **config** ([`CacheConfig`](cache_config.md#id0)) – Cache configuration

#### \_\_init_\_(config=CacheConfig(cache_dir='.cache', cache_file='cache.db', cache_max_size=5000, cache_ttl=300.0, eviction_policy=<EvictionPolicy.LRU: 'lru'>, namespace='default', use_redis=False, redis_url='redis://localhost', redis_port=6379, redis_username='', redis_password='', memory_cache_ttl=60, memory_cache_enabled=True, use_layered_cache=False, cache_layers=[], write_through=True, read_through=True, enable_compression=True, compression_min_size=1024, compression_level=6, disk_usage_monitoring=True, disk_usage_threshold=75.0, disk_critical_threshold=90.0, disk_check_interval=3600, disk_retention_days=30, retry_attempts=3, retry_delay=2, environment=<Environment.DEV: 'dev'>, log_level=<LogLevel.DEBUG: 'debug'>, log_dir='./logs', log_to_file=False, log_max_size=10485760, log_backup_count=5, enable_telemetry=False, telemetry_interval=60, metrics_collection=True, enable_warmup=False, warmup_keys_file=None, warmup_on_start=False, enable_adaptive_ttl=False, adaptive_ttl_min=60, adaptive_ttl_max=86400, access_count_threshold=10, adaptive_ttl_adjustment_factor=1.5, use_distributed_locking=False, lock_timeout=30, lock_retry_attempts=5, lock_retry_interval=0.2, enable_sharding=False, num_shards=1, sharding_algorithm='consistent_hash', enable_invalidation=False, invalidation_channel='cache:invalidation', enable_encryption=False, encryption_key=None, encryption_salt=None, enable_data_signing=False, signing_key=None, signing_algorithm='sha256', enable_access_control=False, redis_ssl=False, redis_ssl_cert_reqs=None, redis_ssl_ca_certs=None, redis_connection_timeout=5.0, redis_max_connections=10, use_redis_sentinel=False, sentinel_master_name='mymaster', sentinel_addresses=[], disk_cache_enabled=True, disk_cache_ttl=3600.0))

Initialize the cache manager with the given configuration.

* **Parameters:**
  **config** ([`CacheConfig`](cache_config.md#id0)) – Cache configuration

#### *async* get(key)

Get a value from the cache.

* **Parameters:**
  **key** (`str`) – The cache key
* **Returns:**
  The cached value or None if not found
* **Return type:**
  Any
* **Raises:**
  **CacheError** – If there’s an error accessing the cache

#### *async* set(key, value, ttl=None)

Set a value in the cache.

* **Parameters:**
  * **key** (`str`) – Cache key
  * **value** (`Any`) – Value to store
  * **ttl** (`Optional`[`float`]) – Time to live in seconds (overrides the default)
* **Returns:**
  True if set successfully, False otherwise
* **Return type:**
  bool
* **Raises:**
  **CacheError** – If there’s an error setting the value in cache

#### *async* delete(key)

Delete a value from the cache.

* **Parameters:**
  **key** (`str`) – The cache key to delete
* **Returns:**
  True if the key was deleted, False if it did not exist
* **Return type:**
  bool
* **Raises:**
  * **CacheConnectionError** – If there’s an error connecting to the cache backend
  * **CacheKeyError** – If the key is invalid

#### *async* clear()

Clear all cache entries from all active layers.

* **Return type:**
  `None`
* **Returns:**
  None

#### get_stats()

Get cache statistics.

* **Returns:**
  Dictionary with cache statistics
* **Return type:**
  Dict[str, Any]

#### cached(ttl=None, key_func=None)

Decorator to cache function results.

* **Parameters:**
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (overrides the default)
  * **key_func** (`Optional`[`Callable`[`...`, `str`]]) – Optional function to generate custom cache keys
* **Return type:**
  `Callable`[[`TypeVar`(`F`, bound= `Callable`[`...`, `Any`])], `TypeVar`(`F`, bound= `Callable`[`...`, `Any`])]
* **Returns:**
  Decorator function

#### *async* invalidate_cached(func, \*args, \*\*kwargs)

Invalidate a cached function result for specific arguments.

* **Parameters:**
  * **func** (`Callable`[`...`, `Any`]) – The decorated function whose cache to invalidate
  * **\*args** (`Any`) – The function arguments
  * **\*\*kwargs** (`Any`) – The function keyword arguments
* **Returns:**
  True if invalidation was successful, False otherwise
* **Return type:**
  bool
* **Raises:**
  **AttributeError** – If the function is not decorated with @cached

#### *async* get_many(keys)

Get multiple values from the cache at once.

* **Parameters:**
  **keys** (`List`[`str`]) – List of cache keys to retrieve
* **Returns:**
  Dictionary mapping keys to their values (only existing keys)
* **Return type:**
  Dict[str, Any]
* **Raises:**
  * **CacheConnectionError** – If there’s an error connecting to the cache backend
  * **CacheSerializationError** – If there’s an error deserializing the data

#### *async* set_many(key_values, expiration=None)

Set multiple values in the cache at once.

* **Parameters:**
  * **key_values** (`Dict`[`str`, `Any`]) – Dictionary mapping keys to values
  * **expiration** (`Optional`[`int`]) – Optional expiration time in seconds
* **Raises:**
  * **CacheConnectionError** – If there’s an error connecting to the cache backend
  * **CacheSerializationError** – If there’s an error serializing the data

#### *async* close()

Close the cache manager and release all resources.

* **Return type:**
  `None`

## CacheManager Class

### *class* src.cache_manager.CacheManager(config=CacheConfig(cache_dir='.cache', cache_file='cache.db', cache_max_size=5000, cache_ttl=300.0, eviction_policy=<EvictionPolicy.LRU: 'lru'>, namespace='default', use_redis=False, redis_url='redis://localhost', redis_port=6379, redis_username='', redis_password='', memory_cache_ttl=60, memory_cache_enabled=True, use_layered_cache=False, cache_layers=[], write_through=True, read_through=True, enable_compression=True, compression_min_size=1024, compression_level=6, disk_usage_monitoring=True, disk_usage_threshold=75.0, disk_critical_threshold=90.0, disk_check_interval=3600, disk_retention_days=30, retry_attempts=3, retry_delay=2, environment=<Environment.DEV: 'dev'>, log_level=<LogLevel.DEBUG: 'debug'>, log_dir='./logs', log_to_file=False, log_max_size=10485760, log_backup_count=5, enable_telemetry=False, telemetry_interval=60, metrics_collection=True, enable_warmup=False, warmup_keys_file=None, warmup_on_start=False, enable_adaptive_ttl=False, adaptive_ttl_min=60, adaptive_ttl_max=86400, access_count_threshold=10, adaptive_ttl_adjustment_factor=1.5, use_distributed_locking=False, lock_timeout=30, lock_retry_attempts=5, lock_retry_interval=0.2, enable_sharding=False, num_shards=1, sharding_algorithm='consistent_hash', enable_invalidation=False, invalidation_channel='cache:invalidation', enable_encryption=False, encryption_key=None, encryption_salt=None, enable_data_signing=False, signing_key=None, signing_algorithm='sha256', enable_access_control=False, redis_ssl=False, redis_ssl_cert_reqs=None, redis_ssl_ca_certs=None, redis_connection_timeout=5.0, redis_max_connections=10, use_redis_sentinel=False, sentinel_master_name='mymaster', sentinel_addresses=[], disk_cache_enabled=True, disk_cache_ttl=3600.0))

Manages caching operations with support for multiple backends.

Features:
- Multiple backend support (in-memory, Redis, shelve)
- TTL (Time-To-Live) for cached items
- Serialization via msgpack (falls back to pickle)
- Thread-safe eviction policies (LRU, FIFO, LFU)
- Namespacing to prevent key collisions
- Circuit breaker pattern to handle backend failures
- In-memory caching layer for performance
- Layered cache approach with read-through/write-through
- Bulk operations (get_many, set_many)
- Function decorator for easy caching
- Compression support for large values

Initialize the cache manager with the given configuration.

* **Parameters:**
  **config** ([`CacheConfig`](cache_config.md#id0)) – Cache configuration

#### \_\_init_\_(config=CacheConfig(cache_dir='.cache', cache_file='cache.db', cache_max_size=5000, cache_ttl=300.0, eviction_policy=<EvictionPolicy.LRU: 'lru'>, namespace='default', use_redis=False, redis_url='redis://localhost', redis_port=6379, redis_username='', redis_password='', memory_cache_ttl=60, memory_cache_enabled=True, use_layered_cache=False, cache_layers=[], write_through=True, read_through=True, enable_compression=True, compression_min_size=1024, compression_level=6, disk_usage_monitoring=True, disk_usage_threshold=75.0, disk_critical_threshold=90.0, disk_check_interval=3600, disk_retention_days=30, retry_attempts=3, retry_delay=2, environment=<Environment.DEV: 'dev'>, log_level=<LogLevel.DEBUG: 'debug'>, log_dir='./logs', log_to_file=False, log_max_size=10485760, log_backup_count=5, enable_telemetry=False, telemetry_interval=60, metrics_collection=True, enable_warmup=False, warmup_keys_file=None, warmup_on_start=False, enable_adaptive_ttl=False, adaptive_ttl_min=60, adaptive_ttl_max=86400, access_count_threshold=10, adaptive_ttl_adjustment_factor=1.5, use_distributed_locking=False, lock_timeout=30, lock_retry_attempts=5, lock_retry_interval=0.2, enable_sharding=False, num_shards=1, sharding_algorithm='consistent_hash', enable_invalidation=False, invalidation_channel='cache:invalidation', enable_encryption=False, encryption_key=None, encryption_salt=None, enable_data_signing=False, signing_key=None, signing_algorithm='sha256', enable_access_control=False, redis_ssl=False, redis_ssl_cert_reqs=None, redis_ssl_ca_certs=None, redis_connection_timeout=5.0, redis_max_connections=10, use_redis_sentinel=False, sentinel_master_name='mymaster', sentinel_addresses=[], disk_cache_enabled=True, disk_cache_ttl=3600.0))

Initialize the cache manager with the given configuration.

* **Parameters:**
  **config** ([`CacheConfig`](cache_config.md#id0)) – Cache configuration

#### *async* get(key)

Get a value from the cache.

* **Parameters:**
  **key** (`str`) – The cache key
* **Returns:**
  The cached value or None if not found
* **Return type:**
  Any
* **Raises:**
  **CacheError** – If there’s an error accessing the cache

#### *async* set(key, value, ttl=None)

Set a value in the cache.

* **Parameters:**
  * **key** (`str`) – Cache key
  * **value** (`Any`) – Value to store
  * **ttl** (`Optional`[`float`]) – Time to live in seconds (overrides the default)
* **Returns:**
  True if set successfully, False otherwise
* **Return type:**
  bool
* **Raises:**
  **CacheError** – If there’s an error setting the value in cache

#### *async* delete(key)

Delete a value from the cache.

* **Parameters:**
  **key** (`str`) – The cache key to delete
* **Returns:**
  True if the key was deleted, False if it did not exist
* **Return type:**
  bool
* **Raises:**
  * **CacheConnectionError** – If there’s an error connecting to the cache backend
  * **CacheKeyError** – If the key is invalid

#### *async* clear()

Clear all cache entries from all active layers.

* **Return type:**
  `None`
* **Returns:**
  None

#### get_stats()

Get cache statistics.

* **Returns:**
  Dictionary with cache statistics
* **Return type:**
  Dict[str, Any]

#### cached(ttl=None, key_func=None)

Decorator to cache function results.

* **Parameters:**
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (overrides the default)
  * **key_func** (`Optional`[`Callable`[`...`, `str`]]) – Optional function to generate custom cache keys
* **Return type:**
  `Callable`[[`TypeVar`(`F`, bound= `Callable`[`...`, `Any`])], `TypeVar`(`F`, bound= `Callable`[`...`, `Any`])]
* **Returns:**
  Decorator function

#### *async* invalidate_cached(func, \*args, \*\*kwargs)

Invalidate a cached function result for specific arguments.

* **Parameters:**
  * **func** (`Callable`[`...`, `Any`]) – The decorated function whose cache to invalidate
  * **\*args** (`Any`) – The function arguments
  * **\*\*kwargs** (`Any`) – The function keyword arguments
* **Returns:**
  True if invalidation was successful, False otherwise
* **Return type:**
  bool
* **Raises:**
  **AttributeError** – If the function is not decorated with @cached

#### *async* get_many(keys)

Get multiple values from the cache at once.

* **Parameters:**
  **keys** (`List`[`str`]) – List of cache keys to retrieve
* **Returns:**
  Dictionary mapping keys to their values (only existing keys)
* **Return type:**
  Dict[str, Any]
* **Raises:**
  * **CacheConnectionError** – If there’s an error connecting to the cache backend
  * **CacheSerializationError** – If there’s an error deserializing the data

#### *async* set_many(key_values, expiration=None)

Set multiple values in the cache at once.

* **Parameters:**
  * **key_values** (`Dict`[`str`, `Any`]) – Dictionary mapping keys to values
  * **expiration** (`Optional`[`int`]) – Optional expiration time in seconds
* **Raises:**
  * **CacheConnectionError** – If there’s an error connecting to the cache backend
  * **CacheSerializationError** – If there’s an error serializing the data

#### *async* \_\_aenter_\_()

Enter async context manager.

* **Returns:**
  Returns self for context manager
* **Return type:**
  [CacheManager](#id0)

#### *async* \_\_aexit_\_(exc_type, exc, tb)

Exit async context manager and clean up resources.

* **Return type:**
  `None`
* **Parameters:**
  * **exc_type** (*type* *|* *None*)
  * **exc** (*Exception* *|* *None*)
  * **tb** (*Any* *|* *None*)

#### *async* close()

Close the cache manager and release all resources.

* **Return type:**
  `None`

### Core Methods

#### *async* CacheManager.get(key)

Get a value from the cache.

* **Parameters:**
  **key** (`str`) – The cache key
* **Returns:**
  The cached value or None if not found
* **Return type:**
  Any
* **Raises:**
  **CacheError** – If there’s an error accessing the cache

#### *async* CacheManager.set(key, value, ttl=None)

Set a value in the cache.

* **Parameters:**
  * **key** (`str`) – Cache key
  * **value** (`Any`) – Value to store
  * **ttl** (`Optional`[`float`]) – Time to live in seconds (overrides the default)
* **Returns:**
  True if set successfully, False otherwise
* **Return type:**
  bool
* **Raises:**
  **CacheError** – If there’s an error setting the value in cache

#### *async* CacheManager.delete(key)

Delete a value from the cache.

* **Parameters:**
  **key** (`str`) – The cache key to delete
* **Returns:**
  True if the key was deleted, False if it did not exist
* **Return type:**
  bool
* **Raises:**
  * **CacheConnectionError** – If there’s an error connecting to the cache backend
  * **CacheKeyError** – If the key is invalid

#### *async* CacheManager.clear()

Clear all cache entries from all active layers.

* **Return type:**
  `None`
* **Returns:**
  None

#### *async* CacheManager.close()

Close the cache manager and release all resources.

* **Return type:**
  `None`

### Batch Operations

#### *async* CacheManager.get_many(keys)

Get multiple values from the cache at once.

* **Parameters:**
  **keys** (`List`[`str`]) – List of cache keys to retrieve
* **Returns:**
  Dictionary mapping keys to their values (only existing keys)
* **Return type:**
  Dict[str, Any]
* **Raises:**
  * **CacheConnectionError** – If there’s an error connecting to the cache backend
  * **CacheSerializationError** – If there’s an error deserializing the data

#### *async* CacheManager.set_many(key_values, expiration=None)

Set multiple values in the cache at once.

* **Parameters:**
  * **key_values** (`Dict`[`str`, `Any`]) – Dictionary mapping keys to values
  * **expiration** (`Optional`[`int`]) – Optional expiration time in seconds
* **Raises:**
  * **CacheConnectionError** – If there’s an error connecting to the cache backend
  * **CacheSerializationError** – If there’s an error serializing the data

### Statistics and Monitoring

#### CacheManager.get_stats()

Get cache statistics.

* **Returns:**
  Dictionary with cache statistics
* **Return type:**
  Dict[str, Any]

### Decorators

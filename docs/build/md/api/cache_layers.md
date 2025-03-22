# Cache Layers

Classes that implement different storage backends for the cache system.

<a id="module-src.cache_layers"></a>

Cache layer implementations for different storage backends.

### *class* src.cache_layers.BaseCacheLayer(namespace, ttl)

Bases: `ABC`

Abstract base class that defines the interface for all cache layers.

All cache layer implementations must extend this class and implement
the required methods.

Initialize the cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values

#### \_\_init_\_(namespace, ttl)

Initialize the cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values

#### *abstractmethod async* clear()

Clear all values in this cache layer.

* **Returns:**
  True if cleared successfully
* **Return type:**
  bool

#### *abstractmethod async* close()

Close connections and release resources.

Should be called when the cache layer is no longer needed.

* **Return type:**
  `None`

#### *abstractmethod async* delete(key)

Delete a value from the cache layer.

* **Parameters:**
  **key** (`str`) – The cache key (already namespaced)
* **Returns:**
  True if deleted successfully
* **Return type:**
  bool

#### *abstractmethod async* get(key)

Get a value from the cache layer.

* **Parameters:**
  **key** (`str`) – The cache key (already namespaced)
* **Returns:**
  (found, value) tuple
* **Return type:**
  Tuple[bool, Any]

#### *abstractmethod async* get_many(keys)

Get multiple values from the cache layer.

* **Parameters:**
  **keys** (`List`[`str`]) – List of cache keys (already namespaced)
* **Returns:**
  Dictionary mapping keys to their values
* **Return type:**
  Dict[str, Any]

#### *abstractmethod async* set(key, value, ttl=None)

Set a value in the cache layer.

* **Parameters:**
  * **key** (`str`) – The cache key (already namespaced)
  * **value** (`Any`) – The value to cache
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if set successfully
* **Return type:**
  bool

#### *abstractmethod async* set_many(key_values, ttl=None)

Set multiple values in the cache layer.

* **Parameters:**
  * **key_values** (`Dict`[`str`, `Any`]) – Dictionary mapping keys to values
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if all values were set successfully
* **Return type:**
  bool

### *class* src.cache_layers.MemoryLayer(namespace, ttl, max_size=1000, eviction_policy=EvictionPolicy.LRU)

Bases: [`BaseCacheLayer`](#src.cache_layers.base_layer.BaseCacheLayer)

In-memory cache layer implementation.

This layer stores cache data in memory for fast access. Data is lost when the
process exits.

Initialize the memory cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values
  * **max_size** (`int`) – Maximum number of items to store in the cache
  * **eviction_policy** ([`EvictionPolicy`](eviction_policies.md#src.cache_config.EvictionPolicy)) – Policy for evicting items when cache is full

#### \_\_init_\_(namespace, ttl, max_size=1000, eviction_policy=EvictionPolicy.LRU)

Initialize the memory cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values
  * **max_size** (`int`) – Maximum number of items to store in the cache
  * **eviction_policy** ([`EvictionPolicy`](eviction_policies.md#src.cache_config.EvictionPolicy)) – Policy for evicting items when cache is full

#### *async* clear()

Clear all values in the memory cache.

* **Returns:**
  True if cleared successfully
* **Return type:**
  bool

#### *async* close()

Close the memory cache layer.

For memory cache, this is a no-op as there are no connections to close.

* **Return type:**
  `None`

#### *async* delete(key)

Delete a value from the memory cache.

* **Parameters:**
  **key** (`str`) – The cache key
* **Returns:**
  True if deleted successfully
* **Return type:**
  bool

#### *async* get(key)

Get a value from the memory cache.

* **Parameters:**
  **key** (`str`) – The cache key
* **Returns:**
  (found, value) tuple
* **Return type:**
  Tuple[bool, Any]

#### *async* get_many(keys)

Get multiple values from the memory cache.

* **Parameters:**
  **keys** (`List`[`str`]) – List of cache keys
* **Returns:**
  Dictionary mapping keys to their values
* **Return type:**
  Dict[str, Any]

#### *async* set(key, value, ttl=None)

Set a value in the memory cache.

* **Parameters:**
  * **key** (`str`) – The cache key
  * **value** (`Any`) – The value to cache
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if set successfully
* **Return type:**
  bool

#### *async* set_many(key_values, ttl=None)

Set multiple values in the memory cache.

* **Parameters:**
  * **key_values** (`Dict`[`str`, `Any`]) – Dictionary mapping keys to values
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if all values were set successfully
* **Return type:**
  bool

### *class* src.cache_layers.RedisLayer(namespace, ttl, redis_url, retry_attempts=3, retry_delay=2, enable_compression=False, compression_min_size=1024, compression_level=6)

Bases: [`BaseCacheLayer`](#src.cache_layers.base_layer.BaseCacheLayer)

Redis cache layer implementation.

This layer stores cache data in a Redis server for shared access across
multiple processes or machines.

Initialize the Redis cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values
  * **redis_url** (`str`) – URL for connecting to Redis server
  * **retry_attempts** (`int`) – Number of retry attempts for Redis operations
  * **retry_delay** (`int`) – Delay between retries in seconds
  * **enable_compression** (`bool`) – Whether to enable compression
  * **compression_min_size** (`int`) – Minimum size for compression to be applied
  * **compression_level** (`int`) – Compression level (1-9) for zlib

#### \_\_init_\_(namespace, ttl, redis_url, retry_attempts=3, retry_delay=2, enable_compression=False, compression_min_size=1024, compression_level=6)

Initialize the Redis cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values
  * **redis_url** (`str`) – URL for connecting to Redis server
  * **retry_attempts** (`int`) – Number of retry attempts for Redis operations
  * **retry_delay** (`int`) – Delay between retries in seconds
  * **enable_compression** (`bool`) – Whether to enable compression
  * **compression_min_size** (`int`) – Minimum size for compression to be applied
  * **compression_level** (`int`) – Compression level (1-9) for zlib

#### *async* clear()

Clear all values in this Redis cache.

Only clears keys with this instance’s namespace.

* **Returns:**
  True if cleared successfully
* **Return type:**
  bool

#### *async* close()

Close the Redis client and release resources.

* **Return type:**
  `None`

#### *async* delete(key)

Delete a value from the Redis cache.

* **Parameters:**
  **key** (`str`) – The cache key
* **Returns:**
  True if deleted successfully
* **Return type:**
  bool

#### *async* get(key)

Get a value from the Redis cache.

* **Parameters:**
  **key** (`str`) – The cache key
* **Returns:**
  (found, value) tuple
* **Return type:**
  Tuple[bool, Any]

#### *async* get_many(keys)

Get multiple values from the Redis cache.

* **Parameters:**
  **keys** (`List`[`str`]) – List of cache keys
* **Returns:**
  Dictionary mapping keys to their values
* **Return type:**
  Dict[str, Any]

#### *async* set(key, value, ttl=None)

Set a value in the Redis cache.

* **Parameters:**
  * **key** (`str`) – The cache key
  * **value** (`Any`) – The value to cache
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if set successfully
* **Return type:**
  bool

#### *async* set_many(key_values, ttl=None)

Set multiple values in the Redis cache.

* **Parameters:**
  * **key_values** (`Dict`[`str`, `Any`]) – Dictionary mapping keys to values
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if all values were set successfully
* **Return type:**
  bool

### *class* src.cache_layers.DiskLayer(namespace, ttl, cache_dir, cache_file, retry_attempts=3, retry_delay=2)

Bases: [`BaseCacheLayer`](#src.cache_layers.base_layer.BaseCacheLayer)

Disk-based cache layer implementation using Python’s shelve.

This layer stores cache data on disk for persistence across process restarts.

Initialize the disk cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values
  * **cache_dir** (`str`) – Directory to store cache files
  * **cache_file** (`str`) – Name of the cache file
  * **retry_attempts** (`int`) – Number of retry attempts for disk operations
  * **retry_delay** (`int`) – Delay between retries in seconds

#### \_\_init_\_(namespace, ttl, cache_dir, cache_file, retry_attempts=3, retry_delay=2)

Initialize the disk cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values
  * **cache_dir** (`str`) – Directory to store cache files
  * **cache_file** (`str`) – Name of the cache file
  * **retry_attempts** (`int`) – Number of retry attempts for disk operations
  * **retry_delay** (`int`) – Delay between retries in seconds

#### *async* clear()

Clear all values in the disk cache.

Only clears keys with this instance’s namespace.

* **Returns:**
  True if cleared successfully
* **Return type:**
  bool

#### *async* close()

Close the disk cache and save metadata.

This should be called when the cache is no longer needed.

* **Return type:**
  `None`

#### *async* delete(key)

Delete a value from the disk cache.

* **Parameters:**
  **key** (`str`) – The cache key (already namespaced)
* **Returns:**
  True if deleted successfully
* **Return type:**
  bool

#### *async* get(key)

Get a value from the disk cache.

* **Parameters:**
  **key** (`str`) – The cache key (already namespaced)
* **Returns:**
  (found, value) tuple
* **Return type:**
  Tuple[bool, Any]

#### *async* get_many(keys)

Get multiple values from the disk cache.

* **Parameters:**
  **keys** (`List`[`str`]) – List of cache keys (already namespaced)
* **Returns:**
  Dictionary mapping keys to their values
* **Return type:**
  Dict[str, Any]

#### *async* set(key, value, ttl=None)

Set a value in the disk cache.

* **Parameters:**
  * **key** (`str`) – The cache key (already namespaced)
  * **value** (`Any`) – The value to cache
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if set successfully
* **Return type:**
  bool

#### *async* set_many(key_values, ttl=None)

Set multiple values in the disk cache.

* **Parameters:**
  * **key_values** (`Dict`[`str`, `Any`]) – Dictionary mapping keys to values
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if all values were set successfully
* **Return type:**
  bool

## Base Layer

Base abstract class for cache layers implementation.

### *class* src.cache_layers.base_layer.BaseCacheLayer(namespace, ttl)

Bases: `ABC`

Abstract base class that defines the interface for all cache layers.

All cache layer implementations must extend this class and implement
the required methods.

Initialize the cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values

#### \_\_init_\_(namespace, ttl)

Initialize the cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values

#### *abstractmethod async* get(key)

Get a value from the cache layer.

* **Parameters:**
  **key** (`str`) – The cache key (already namespaced)
* **Returns:**
  (found, value) tuple
* **Return type:**
  Tuple[bool, Any]

#### *abstractmethod async* set(key, value, ttl=None)

Set a value in the cache layer.

* **Parameters:**
  * **key** (`str`) – The cache key (already namespaced)
  * **value** (`Any`) – The value to cache
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if set successfully
* **Return type:**
  bool

#### *abstractmethod async* delete(key)

Delete a value from the cache layer.

* **Parameters:**
  **key** (`str`) – The cache key (already namespaced)
* **Returns:**
  True if deleted successfully
* **Return type:**
  bool

#### *abstractmethod async* get_many(keys)

Get multiple values from the cache layer.

* **Parameters:**
  **keys** (`List`[`str`]) – List of cache keys (already namespaced)
* **Returns:**
  Dictionary mapping keys to their values
* **Return type:**
  Dict[str, Any]

#### *abstractmethod async* set_many(key_values, ttl=None)

Set multiple values in the cache layer.

* **Parameters:**
  * **key_values** (`Dict`[`str`, `Any`]) – Dictionary mapping keys to values
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if all values were set successfully
* **Return type:**
  bool

#### *abstractmethod async* clear()

Clear all values in this cache layer.

* **Returns:**
  True if cleared successfully
* **Return type:**
  bool

#### *abstractmethod async* close()

Close connections and release resources.

Should be called when the cache layer is no longer needed.

* **Return type:**
  `None`

## Memory Layer

In-memory cache layer implementation.

### *class* src.cache_layers.memory_layer.MemoryLayer(namespace, ttl, max_size=1000, eviction_policy=EvictionPolicy.LRU)

Bases: [`BaseCacheLayer`](#src.cache_layers.base_layer.BaseCacheLayer)

In-memory cache layer implementation.

This layer stores cache data in memory for fast access. Data is lost when the
process exits.

Initialize the memory cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values
  * **max_size** (`int`) – Maximum number of items to store in the cache
  * **eviction_policy** ([`EvictionPolicy`](eviction_policies.md#src.cache_config.EvictionPolicy)) – Policy for evicting items when cache is full

#### \_\_init_\_(namespace, ttl, max_size=1000, eviction_policy=EvictionPolicy.LRU)

Initialize the memory cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values
  * **max_size** (`int`) – Maximum number of items to store in the cache
  * **eviction_policy** ([`EvictionPolicy`](eviction_policies.md#src.cache_config.EvictionPolicy)) – Policy for evicting items when cache is full

#### *async* get(key)

Get a value from the memory cache.

* **Parameters:**
  **key** (`str`) – The cache key
* **Returns:**
  (found, value) tuple
* **Return type:**
  Tuple[bool, Any]

#### *async* set(key, value, ttl=None)

Set a value in the memory cache.

* **Parameters:**
  * **key** (`str`) – The cache key
  * **value** (`Any`) – The value to cache
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if set successfully
* **Return type:**
  bool

#### *async* delete(key)

Delete a value from the memory cache.

* **Parameters:**
  **key** (`str`) – The cache key
* **Returns:**
  True if deleted successfully
* **Return type:**
  bool

#### *async* get_many(keys)

Get multiple values from the memory cache.

* **Parameters:**
  **keys** (`List`[`str`]) – List of cache keys
* **Returns:**
  Dictionary mapping keys to their values
* **Return type:**
  Dict[str, Any]

#### *async* set_many(key_values, ttl=None)

Set multiple values in the memory cache.

* **Parameters:**
  * **key_values** (`Dict`[`str`, `Any`]) – Dictionary mapping keys to values
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if all values were set successfully
* **Return type:**
  bool

#### *async* clear()

Clear all values in the memory cache.

* **Returns:**
  True if cleared successfully
* **Return type:**
  bool

#### *async* close()

Close the memory cache layer.

For memory cache, this is a no-op as there are no connections to close.

* **Return type:**
  `None`

## Redis Layer

Redis cache layer implementation.

### *class* src.cache_layers.redis_layer.RedisLayer(namespace, ttl, redis_url, retry_attempts=3, retry_delay=2, enable_compression=False, compression_min_size=1024, compression_level=6)

Bases: [`BaseCacheLayer`](#src.cache_layers.base_layer.BaseCacheLayer)

Redis cache layer implementation.

This layer stores cache data in a Redis server for shared access across
multiple processes or machines.

Initialize the Redis cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values
  * **redis_url** (`str`) – URL for connecting to Redis server
  * **retry_attempts** (`int`) – Number of retry attempts for Redis operations
  * **retry_delay** (`int`) – Delay between retries in seconds
  * **enable_compression** (`bool`) – Whether to enable compression
  * **compression_min_size** (`int`) – Minimum size for compression to be applied
  * **compression_level** (`int`) – Compression level (1-9) for zlib

#### \_\_init_\_(namespace, ttl, redis_url, retry_attempts=3, retry_delay=2, enable_compression=False, compression_min_size=1024, compression_level=6)

Initialize the Redis cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values
  * **redis_url** (`str`) – URL for connecting to Redis server
  * **retry_attempts** (`int`) – Number of retry attempts for Redis operations
  * **retry_delay** (`int`) – Delay between retries in seconds
  * **enable_compression** (`bool`) – Whether to enable compression
  * **compression_min_size** (`int`) – Minimum size for compression to be applied
  * **compression_level** (`int`) – Compression level (1-9) for zlib

#### *async* get(key)

Get a value from the Redis cache.

* **Parameters:**
  **key** (`str`) – The cache key
* **Returns:**
  (found, value) tuple
* **Return type:**
  Tuple[bool, Any]

#### *async* set(key, value, ttl=None)

Set a value in the Redis cache.

* **Parameters:**
  * **key** (`str`) – The cache key
  * **value** (`Any`) – The value to cache
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if set successfully
* **Return type:**
  bool

#### *async* delete(key)

Delete a value from the Redis cache.

* **Parameters:**
  **key** (`str`) – The cache key
* **Returns:**
  True if deleted successfully
* **Return type:**
  bool

#### *async* get_many(keys)

Get multiple values from the Redis cache.

* **Parameters:**
  **keys** (`List`[`str`]) – List of cache keys
* **Returns:**
  Dictionary mapping keys to their values
* **Return type:**
  Dict[str, Any]

#### *async* set_many(key_values, ttl=None)

Set multiple values in the Redis cache.

* **Parameters:**
  * **key_values** (`Dict`[`str`, `Any`]) – Dictionary mapping keys to values
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if all values were set successfully
* **Return type:**
  bool

#### *async* clear()

Clear all values in this Redis cache.

Only clears keys with this instance’s namespace.

* **Returns:**
  True if cleared successfully
* **Return type:**
  bool

#### *async* close()

Close the Redis client and release resources.

* **Return type:**
  `None`

## Disk Layer

Disk-based cache layer implementation.

### *class* src.cache_layers.disk_layer.DiskLayer(namespace, ttl, cache_dir, cache_file, retry_attempts=3, retry_delay=2)

Bases: [`BaseCacheLayer`](#src.cache_layers.base_layer.BaseCacheLayer)

Disk-based cache layer implementation using Python’s shelve.

This layer stores cache data on disk for persistence across process restarts.

Initialize the disk cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values
  * **cache_dir** (`str`) – Directory to store cache files
  * **cache_file** (`str`) – Name of the cache file
  * **retry_attempts** (`int`) – Number of retry attempts for disk operations
  * **retry_delay** (`int`) – Delay between retries in seconds

#### \_\_init_\_(namespace, ttl, cache_dir, cache_file, retry_attempts=3, retry_delay=2)

Initialize the disk cache layer.

* **Parameters:**
  * **namespace** (`str`) – Namespace prefix for cache keys
  * **ttl** (`int`) – Default time-to-live in seconds for cached values
  * **cache_dir** (`str`) – Directory to store cache files
  * **cache_file** (`str`) – Name of the cache file
  * **retry_attempts** (`int`) – Number of retry attempts for disk operations
  * **retry_delay** (`int`) – Delay between retries in seconds

#### *async* get(key)

Get a value from the disk cache.

* **Parameters:**
  **key** (`str`) – The cache key (already namespaced)
* **Returns:**
  (found, value) tuple
* **Return type:**
  Tuple[bool, Any]

#### *async* set(key, value, ttl=None)

Set a value in the disk cache.

* **Parameters:**
  * **key** (`str`) – The cache key (already namespaced)
  * **value** (`Any`) – The value to cache
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if set successfully
* **Return type:**
  bool

#### *async* delete(key)

Delete a value from the disk cache.

* **Parameters:**
  **key** (`str`) – The cache key (already namespaced)
* **Returns:**
  True if deleted successfully
* **Return type:**
  bool

#### *async* get_many(keys)

Get multiple values from the disk cache.

* **Parameters:**
  **keys** (`List`[`str`]) – List of cache keys (already namespaced)
* **Returns:**
  Dictionary mapping keys to their values
* **Return type:**
  Dict[str, Any]

#### *async* set_many(key_values, ttl=None)

Set multiple values in the disk cache.

* **Parameters:**
  * **key_values** (`Dict`[`str`, `Any`]) – Dictionary mapping keys to values
  * **ttl** (`Optional`[`int`]) – Time to live in seconds (defaults to layer ttl)
* **Returns:**
  True if all values were set successfully
* **Return type:**
  bool

#### *async* clear()

Clear all values in the disk cache.

Only clears keys with this instance’s namespace.

* **Returns:**
  True if cleared successfully
* **Return type:**
  bool

#### *async* close()

Close the disk cache and save metadata.

This should be called when the cache is no longer needed.

* **Return type:**
  `None`

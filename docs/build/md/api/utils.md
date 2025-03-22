# Utilities

Utility modules for the cache system.

<a id="module-src.utils"></a>

Utility modules for CacheManager.

### *class* src.utils.NamespaceManager(namespace='default')

Bases: `object`

Manages namespacing for cache keys to prevent collisions.

Provides consistent methods for adding and removing namespace prefixes from keys.

Initialize the namespace manager.

* **Parameters:**
  **namespace** (`str`) – The namespace to use for keys

#### \_\_init_\_(namespace='default')

Initialize the namespace manager.

* **Parameters:**
  **namespace** (`str`) – The namespace to use for keys

#### namespace_key(key)

Add namespace prefix to a key.

* **Parameters:**
  **key** (`str`) – The original key
* **Returns:**
  The namespaced key
* **Return type:**
  str

#### namespace_keys_dict(data)

Add namespace prefix to all keys in a dictionary.

* **Parameters:**
  **data** (`Dict`[`str`, `Any`]) – Dictionary with original keys
* **Returns:**
  Dictionary with namespaced keys
* **Return type:**
  Dict[str, Any]

#### remove_namespace(namespaced_key)

Remove namespace prefix from a key.

* **Parameters:**
  **namespaced_key** (`str`) – The namespaced key
* **Returns:**
  The original key without namespace
* **Return type:**
  str

#### remove_namespace_from_keys_dict(data)

Remove namespace prefix from all keys in a dictionary.

* **Parameters:**
  **data** (`Dict`[`str`, `Any`]) – Dictionary with namespaced keys
* **Returns:**
  Dictionary with original keys
* **Return type:**
  Dict[str, Any]

### *class* src.utils.Serializer(enable_compression=False, compression_min_size=1024, compression_level=6, encryptor=None, data_signer=None, stats=None, correlation_id=None)

Bases: `object`

Handles data serialization and deserialization for cache values.

This class provides methods to serialize and deserialize values with msgpack,
with optional compression, encryption, and signing.

Initialize the serializer.

* **Parameters:**
  * **enable_compression** (`bool`) – Whether to enable compression
  * **compression_min_size** (`int`) – Minimum size for compression to be applied
  * **compression_level** (`int`) – Zlib compression level (0-9)
  * **encryptor** – Optional encryptor instance for encryption
  * **data_signer** – Optional data signer instance for signing
  * **stats** (`Optional`[`Dict`[`str`, `int`]]) – Optional dictionary for tracking error statistics
  * **correlation_id** (`str`) – Correlation ID for logging

#### \_\_init_\_(enable_compression=False, compression_min_size=1024, compression_level=6, encryptor=None, data_signer=None, stats=None, correlation_id=None)

Initialize the serializer.

* **Parameters:**
  * **enable_compression** (`bool`) – Whether to enable compression
  * **compression_min_size** (`int`) – Minimum size for compression to be applied
  * **compression_level** (`int`) – Zlib compression level (0-9)
  * **encryptor** – Optional encryptor instance for encryption
  * **data_signer** – Optional data signer instance for signing
  * **stats** (`Optional`[`Dict`[`str`, `int`]]) – Optional dictionary for tracking error statistics
  * **correlation_id** (`str`) – Correlation ID for logging

#### deserialize(data)

Deserialize a value from storage.

Deserializes a value previously serialized with serialize.

* **Parameters:**
  **data** (`bytes`) – The data to deserialize
* **Return type:**
  `Any`
* **Returns:**
  The deserialized value
* **Raises:**
  **CacheSerializationError** – If deserialization fails

#### serialize(value)

Serialize a value for storage.

Serializes the value with msgpack (or pickle if msgpack not available),
and optionally compresses, encrypts, and signs it.

* **Parameters:**
  **value** (`Any`) – The value to serialize
* **Returns:**
  The serialized value
* **Return type:**
  bytes
* **Raises:**
  **CacheSerializationError** – If serialization fails

### *class* src.utils.DiskCacheManager(cache_dir, cache_file, namespace='default', correlation_id=None)

Bases: `object`

Manages disk-based cache operations.

Handles cleanup, compaction, and other disk cache maintenance tasks.

Initialize the disk cache manager.

* **Parameters:**
  * **cache_dir** (`str`) – Directory where cache files are stored
  * **cache_file** (`str`) – Base filename for disk cache
  * **namespace** (`str`) – Cache namespace
  * **correlation_id** (`Optional`[`str`]) – Correlation ID for logging

#### \_\_init_\_(cache_dir, cache_file, namespace='default', correlation_id=None)

Initialize the disk cache manager.

* **Parameters:**
  * **cache_dir** (`str`) – Directory where cache files are stored
  * **cache_file** (`str`) – Base filename for disk cache
  * **namespace** (`str`) – Cache namespace
  * **correlation_id** (`Optional`[`str`]) – Correlation ID for logging

#### *async* clean_disk_cache(retention_days, aggressive=False)

Clean up the disk cache by removing oldest entries.

* **Parameters:**
  * **retention_days** (`int`) – How many days of data to retain
  * **aggressive** (`bool`) – If True, perform more aggressive cleanup
* **Returns:**
  Number of items removed
* **Return type:**
  int

#### *async* compact_cache()

Compact the disk cache to reclaim space.

This removes fragmentation and frees up disk space.

* **Returns:**
  True if compaction was successful
* **Return type:**
  bool

#### get_disk_usage()

Get current disk cache usage as percentage.

* **Returns:**
  Disk usage as percentage (0-100)
* **Return type:**
  float

### *class* src.utils.CacheInitializer(config, correlation_id)

Bases: `object`

Helper class for initializing CacheManager components.

This class encapsulates the initialization logic for different components
of the CacheManager, like cache layers, telemetry, encryption, etc.

Initialize the CacheInitializer.

* **Parameters:**
  * **config** ([`CacheConfig`](cache_config.md#id0)) – The configuration to use for initialization
  * **correlation_id** (`str`) – A unique identifier for logging and tracing

#### \_\_init_\_(config, correlation_id)

Initialize the CacheInitializer.

* **Parameters:**
  * **config** ([`CacheConfig`](cache_config.md#id0)) – The configuration to use for initialization
  * **correlation_id** (`str`) – A unique identifier for logging and tracing

#### setup_cache_layers()

Set up cache layers based on configuration.

* **Return type:**
  `Dict`[`str`, `Any`]
* **Returns:**
  Dictionary containing cache layer instances and related components

#### setup_core_components(redis_client=None)

Set up core components like telemetry, security, etc.

* **Parameters:**
  **redis_client** – Optional Redis client for components that need it
* **Return type:**
  `Dict`[`str`, `Any`]
* **Returns:**
  Dictionary containing core component instances

### src.utils.compress_data(value, config)

Compress data if it’s large enough.

* **Parameters:**
  * **value** (`Any`) – The data to potentially compress
  * **config** (`Any`) – Configuration object with compression settings
* **Returns:**
  Compressed data or original data if compression isn’t applicable
* **Return type:**
  Any

### src.utils.decompress_data(value, config)

Decompress data that was previously compressed.

* **Parameters:**
  * **value** (`Any`) – The potentially compressed data
  * **config** (`Any`) – Configuration object with compression settings
* **Returns:**
  Decompressed data or original data if not compressed
* **Return type:**
  Any

## Namespacing

Utility for managing namespaced cache keys.

### *class* src.utils.namespacing.NamespaceManager(namespace='default')

Bases: `object`

Manages namespacing for cache keys to prevent collisions.

Provides consistent methods for adding and removing namespace prefixes from keys.

Initialize the namespace manager.

* **Parameters:**
  **namespace** (`str`) – The namespace to use for keys

#### \_\_init_\_(namespace='default')

Initialize the namespace manager.

* **Parameters:**
  **namespace** (`str`) – The namespace to use for keys

#### namespace_key(key)

Add namespace prefix to a key.

* **Parameters:**
  **key** (`str`) – The original key
* **Returns:**
  The namespaced key
* **Return type:**
  str

#### remove_namespace(namespaced_key)

Remove namespace prefix from a key.

* **Parameters:**
  **namespaced_key** (`str`) – The namespaced key
* **Returns:**
  The original key without namespace
* **Return type:**
  str

#### namespace_keys_dict(data)

Add namespace prefix to all keys in a dictionary.

* **Parameters:**
  **data** (`Dict`[`str`, `Any`]) – Dictionary with original keys
* **Returns:**
  Dictionary with namespaced keys
* **Return type:**
  Dict[str, Any]

#### remove_namespace_from_keys_dict(data)

Remove namespace prefix from all keys in a dictionary.

* **Parameters:**
  **data** (`Dict`[`str`, `Any`]) – Dictionary with namespaced keys
* **Returns:**
  Dictionary with original keys
* **Return type:**
  Dict[str, Any]

## Serialization

Serialization utilities for CacheManager.

### *class* src.utils.serialization.Serializer(enable_compression=False, compression_min_size=1024, compression_level=6, encryptor=None, data_signer=None, stats=None, correlation_id=None)

Bases: `object`

Handles data serialization and deserialization for cache values.

This class provides methods to serialize and deserialize values with msgpack,
with optional compression, encryption, and signing.

Initialize the serializer.

* **Parameters:**
  * **enable_compression** (`bool`) – Whether to enable compression
  * **compression_min_size** (`int`) – Minimum size for compression to be applied
  * **compression_level** (`int`) – Zlib compression level (0-9)
  * **encryptor** – Optional encryptor instance for encryption
  * **data_signer** – Optional data signer instance for signing
  * **stats** (`Optional`[`Dict`[`str`, `int`]]) – Optional dictionary for tracking error statistics
  * **correlation_id** (`str`) – Correlation ID for logging

#### \_\_init_\_(enable_compression=False, compression_min_size=1024, compression_level=6, encryptor=None, data_signer=None, stats=None, correlation_id=None)

Initialize the serializer.

* **Parameters:**
  * **enable_compression** (`bool`) – Whether to enable compression
  * **compression_min_size** (`int`) – Minimum size for compression to be applied
  * **compression_level** (`int`) – Zlib compression level (0-9)
  * **encryptor** – Optional encryptor instance for encryption
  * **data_signer** – Optional data signer instance for signing
  * **stats** (`Optional`[`Dict`[`str`, `int`]]) – Optional dictionary for tracking error statistics
  * **correlation_id** (`str`) – Correlation ID for logging

#### serialize(value)

Serialize a value for storage.

Serializes the value with msgpack (or pickle if msgpack not available),
and optionally compresses, encrypts, and signs it.

* **Parameters:**
  **value** (`Any`) – The value to serialize
* **Returns:**
  The serialized value
* **Return type:**
  bytes
* **Raises:**
  **CacheSerializationError** – If serialization fails

#### deserialize(data)

Deserialize a value from storage.

Deserializes a value previously serialized with serialize.

* **Parameters:**
  **data** (`bytes`) – The data to deserialize
* **Return type:**
  `Any`
* **Returns:**
  The deserialized value
* **Raises:**
  **CacheSerializationError** – If deserialization fails

### src.utils.serialization.serialize(value, enable_compression=False, compression_min_size=1024, compression_level=6)

Serialize a value using msgpack if available, otherwise pickle.

* **Parameters:**
  * **value** (`Any`) – The value to serialize
  * **enable_compression** (`bool`) – Whether to enable compression for large values
  * **compression_min_size** (`int`) – Minimum size in bytes for compression to be applied
  * **compression_level** (`int`) – Compression level (1-9) for zlib
* **Returns:**
  The serialized value
* **Return type:**
  bytes
* **Raises:**
  **CacheSerializationError** – If serialization fails

### src.utils.serialization.deserialize(data)

Deserialize a value using msgpack if available, otherwise pickle.

* **Parameters:**
  **data** (`bytes`) – The serialized data
* **Returns:**
  The deserialized value
* **Return type:**
  Any
* **Raises:**
  **CacheSerializationError** – If deserialization fails

## Disk Cache

Utility for managing disk cache operations.

### *class* src.utils.disk_cache.DiskCacheManager(cache_dir, cache_file, namespace='default', correlation_id=None)

Bases: `object`

Manages disk-based cache operations.

Handles cleanup, compaction, and other disk cache maintenance tasks.

Initialize the disk cache manager.

* **Parameters:**
  * **cache_dir** (`str`) – Directory where cache files are stored
  * **cache_file** (`str`) – Base filename for disk cache
  * **namespace** (`str`) – Cache namespace
  * **correlation_id** (`Optional`[`str`]) – Correlation ID for logging

#### \_\_init_\_(cache_dir, cache_file, namespace='default', correlation_id=None)

Initialize the disk cache manager.

* **Parameters:**
  * **cache_dir** (`str`) – Directory where cache files are stored
  * **cache_file** (`str`) – Base filename for disk cache
  * **namespace** (`str`) – Cache namespace
  * **correlation_id** (`Optional`[`str`]) – Correlation ID for logging

#### get_disk_usage()

Get current disk cache usage as percentage.

* **Returns:**
  Disk usage as percentage (0-100)
* **Return type:**
  float

#### *async* clean_disk_cache(retention_days, aggressive=False)

Clean up the disk cache by removing oldest entries.

* **Parameters:**
  * **retention_days** (`int`) – How many days of data to retain
  * **aggressive** (`bool`) – If True, perform more aggressive cleanup
* **Returns:**
  Number of items removed
* **Return type:**
  int

#### *async* compact_cache()

Compact the disk cache to reclaim space.

This removes fragmentation and frees up disk space.

* **Returns:**
  True if compaction was successful
* **Return type:**
  bool

## Initialization

Utility for initializing CacheManager components.

### *class* src.utils.initialization.CacheInitializer(config, correlation_id)

Bases: `object`

Helper class for initializing CacheManager components.

This class encapsulates the initialization logic for different components
of the CacheManager, like cache layers, telemetry, encryption, etc.

Initialize the CacheInitializer.

* **Parameters:**
  * **config** ([`CacheConfig`](cache_config.md#id0)) – The configuration to use for initialization
  * **correlation_id** (`str`) – A unique identifier for logging and tracing

#### \_\_init_\_(config, correlation_id)

Initialize the CacheInitializer.

* **Parameters:**
  * **config** ([`CacheConfig`](cache_config.md#id0)) – The configuration to use for initialization
  * **correlation_id** (`str`) – A unique identifier for logging and tracing

#### setup_cache_layers()

Set up cache layers based on configuration.

* **Return type:**
  `Dict`[`str`, `Any`]
* **Returns:**
  Dictionary containing cache layer instances and related components

#### setup_core_components(redis_client=None)

Set up core components like telemetry, security, etc.

* **Parameters:**
  **redis_client** – Optional Redis client for components that need it
* **Return type:**
  `Dict`[`str`, `Any`]
* **Returns:**
  Dictionary containing core component instances

## Compression

Utility functions for data compression and decompression.

### src.utils.compression.compress_data(value, config)

Compress data if it’s large enough.

* **Parameters:**
  * **value** (`Any`) – The data to potentially compress
  * **config** (`Any`) – Configuration object with compression settings
* **Returns:**
  Compressed data or original data if compression isn’t applicable
* **Return type:**
  Any

### src.utils.compression.decompress_data(value, config)

Decompress data that was previously compressed.

* **Parameters:**
  * **value** (`Any`) – The potentially compressed data
  * **config** (`Any`) – Configuration object with compression settings
* **Returns:**
  Decompressed data or original data if not compressed
* **Return type:**
  Any

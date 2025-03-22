# Cache Configuration

The module that defines configuration options for the cache system.

<a id="module-src.cache_config"></a>

### *class* src.cache_config.EvictionPolicy(\*values)

Bases: `str`, `Enum`

Enum defining cache eviction policies.

Available policies:
- LRU: Least Recently Used - evicts least recently accessed items first
- FIFO: First In First Out - evicts oldest items first
- LFU: Least Frequently Used - evicts least frequently accessed items

#### LRU *= 'lru'*

#### FIFO *= 'fifo'*

#### LFU *= 'lfu'*

### *class* src.cache_config.CacheLayerType(\*values)

Bases: `str`, `Enum`

Enum defining cache layer types.

Available types:
- MEMORY: In-memory cache (fastest, but volatile)
- REDIS: Redis cache (networked, shared across instances)
- DISK: Local disk storage via shelve (persistent, but slow)

#### MEMORY *= 'memory'*

#### REDIS *= 'redis'*

#### DISK *= 'disk'*

### *class* src.cache_config.LogLevel(\*values)

Bases: `str`, `Enum`

Enum defining log levels.

Available levels:
- DEBUG: Detailed debugging information
- INFO: Confirmation that things are working as expected
- WARNING: Indication that something unexpected happened
- ERROR: Due to a more serious problem, the software hasn’t been able to perform a function
- CRITICAL: A serious error indicating the program may be unable to continue running

#### DEBUG *= 'debug'*

#### INFO *= 'info'*

#### WARNING *= 'warning'*

#### ERROR *= 'error'*

#### CRITICAL *= 'critical'*

### *class* src.cache_config.Environment(\*values)

Bases: `str`, `Enum`

Enum defining environment types.

Available environments:
- DEV: Development environment
- TEST: Testing environment
- PROD: Production environment

#### DEV *= 'dev'*

#### TEST *= 'test'*

#### PROD *= 'prod'*

### *class* src.cache_config.CacheLayerConfig(\*\*data)

Bases: `BaseModel`

Configuration for a single cache layer.

Defines the type, TTL, and other settings for a specific cache layer.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **type** ([*CacheLayerType*](#id94))
  * **ttl** (*int*)
  * **enabled** (*bool*)
  * **weight** (*int*)
  * **max_size** (*int* *|* *None*)

#### type *: [`CacheLayerType`](#id94)*

#### ttl *: `int`*

#### enabled *: `bool`*

#### weight *: `int`*

#### max_size *: `Optional`[`int`]*

#### model_config *: ClassVar[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [ConfigDict][pydantic.config.ConfigDict].

### *class* src.cache_config.CacheConfig(\*\*data)

Bases: `BaseModel`

Configuration for the CacheManager.

Provides settings for cache storage, Redis connection, and retry behavior.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **cache_dir** (*str*)
  * **cache_file** (*str*)
  * **cache_max_size** (*int*)
  * **cache_ttl** (*float*)
  * **eviction_policy** ([*EvictionPolicy*](eviction_policies.md#src.cache_config.EvictionPolicy))
  * **namespace** (*str*)
  * **use_redis** (*bool*)
  * **redis_url** (*str*)
  * **redis_port** (*int*)
  * **redis_username** (*str*)
  * **redis_password** (*str*)
  * **memory_cache_ttl** (*int*)
  * **memory_cache_enabled** (*bool*)
  * **use_layered_cache** (*bool*)
  * **cache_layers** (*List* *[*[*CacheLayerConfig*](#id83) *]*)
  * **write_through** (*bool*)
  * **read_through** (*bool*)
  * **enable_compression** (*bool*)
  * **compression_min_size** (*int*)
  * **compression_level** (*int*)
  * **disk_usage_monitoring** (*bool*)
  * **disk_usage_threshold** (*float*)
  * **disk_critical_threshold** (*float*)
  * **disk_check_interval** (*int*)
  * **disk_retention_days** (*int*)
  * **retry_attempts** (*int*)
  * **retry_delay** (*int*)
  * **environment** ([*Environment*](#id104))
  * **log_level** ([*LogLevel*](#id98))
  * **log_dir** (*str*)
  * **log_to_file** (*bool*)
  * **log_max_size** (*int*)
  * **log_backup_count** (*int*)
  * **enable_telemetry** (*bool*)
  * **telemetry_interval** (*int*)
  * **metrics_collection** (*bool*)
  * **enable_warmup** (*bool*)
  * **warmup_keys_file** (*str* *|* *None*)
  * **warmup_on_start** (*bool*)
  * **enable_adaptive_ttl** (*bool*)
  * **adaptive_ttl_min** (*int*)
  * **adaptive_ttl_max** (*int*)
  * **access_count_threshold** (*int*)
  * **adaptive_ttl_adjustment_factor** (*float*)
  * **use_distributed_locking** (*bool*)
  * **lock_timeout** (*int*)
  * **lock_retry_attempts** (*int*)
  * **lock_retry_interval** (*float*)
  * **enable_sharding** (*bool*)
  * **num_shards** (*int*)
  * **sharding_algorithm** (*str*)
  * **enable_invalidation** (*bool*)
  * **invalidation_channel** (*str*)
  * **enable_encryption** (*bool*)
  * **encryption_key** (*str* *|* *None*)
  * **encryption_salt** (*str* *|* *None*)
  * **enable_data_signing** (*bool*)
  * **signing_key** (*str* *|* *None*)
  * **signing_algorithm** (*str*)
  * **enable_access_control** (*bool*)
  * **redis_ssl** (*bool*)
  * **redis_ssl_cert_reqs** (*str* *|* *None*)
  * **redis_ssl_ca_certs** (*str* *|* *None*)
  * **redis_connection_timeout** (*float*)
  * **redis_max_connections** (*int*)
  * **use_redis_sentinel** (*bool*)
  * **sentinel_master_name** (*str*)
  * **sentinel_addresses** (*List* *[**str* *]*)
  * **disk_cache_enabled** (*bool*)
  * **disk_cache_ttl** (*float*)

#### cache_dir *: `str`*

#### cache_file *: `str`*

#### cache_max_size *: `int`*

#### cache_ttl *: `float`*

#### eviction_policy *: [`EvictionPolicy`](eviction_policies.md#src.cache_config.EvictionPolicy)*

#### namespace *: `str`*

#### use_redis *: `bool`*

#### redis_url *: `str`*

#### redis_port *: `int`*

#### redis_username *: `str`*

#### redis_password *: `str`*

#### memory_cache_ttl *: `int`*

#### memory_cache_enabled *: `bool`*

#### use_layered_cache *: `bool`*

#### cache_layers *: `List`[[`CacheLayerConfig`](#id83)]*

#### write_through *: `bool`*

#### read_through *: `bool`*

#### enable_compression *: `bool`*

#### compression_min_size *: `int`*

#### compression_level *: `int`*

#### disk_usage_monitoring *: `bool`*

#### disk_usage_threshold *: `float`*

#### disk_critical_threshold *: `float`*

#### disk_check_interval *: `int`*

#### disk_retention_days *: `int`*

#### retry_attempts *: `int`*

#### retry_delay *: `int`*

#### environment *: [`Environment`](#id104)*

#### log_level *: [`LogLevel`](#id98)*

#### log_dir *: `str`*

#### log_to_file *: `bool`*

#### log_max_size *: `int`*

#### log_backup_count *: `int`*

#### enable_telemetry *: `bool`*

#### telemetry_interval *: `int`*

#### metrics_collection *: `bool`*

#### enable_warmup *: `bool`*

#### warmup_keys_file *: `Optional`[`str`]*

#### warmup_on_start *: `bool`*

#### enable_adaptive_ttl *: `bool`*

#### adaptive_ttl_min *: `int`*

#### adaptive_ttl_max *: `int`*

#### access_count_threshold *: `int`*

#### adaptive_ttl_adjustment_factor *: `float`*

#### use_distributed_locking *: `bool`*

#### lock_timeout *: `int`*

#### lock_retry_attempts *: `int`*

#### lock_retry_interval *: `float`*

#### enable_sharding *: `bool`*

#### num_shards *: `int`*

#### sharding_algorithm *: `str`*

#### enable_invalidation *: `bool`*

#### invalidation_channel *: `str`*

#### enable_encryption *: `bool`*

#### encryption_key *: `Optional`[`str`]*

#### encryption_salt *: `Optional`[`str`]*

#### enable_data_signing *: `bool`*

#### signing_key *: `Optional`[`str`]*

#### signing_algorithm *: `str`*

#### enable_access_control *: `bool`*

#### redis_ssl *: `bool`*

#### redis_ssl_cert_reqs *: `Optional`[`str`]*

#### redis_ssl_ca_certs *: `Optional`[`str`]*

#### redis_connection_timeout *: `float`*

#### redis_max_connections *: `int`*

#### use_redis_sentinel *: `bool`*

#### sentinel_master_name *: `str`*

#### sentinel_addresses *: `List`[`str`]*

#### disk_cache_enabled *: `bool`*

#### disk_cache_ttl *: `float`*

#### *classmethod* validate_positive_int(v)

Validate that integer fields are positive.

* **Return type:**
  `int`
* **Parameters:**
  **v** (*int*)

#### *classmethod* validate_percentage(v)

Validate that threshold values are valid percentages.

* **Return type:**
  `float`
* **Parameters:**
  **v** (*float*)

#### *classmethod* validate_compression_level(v)

Validate compression level is between 1 and 9.

* **Return type:**
  `int`
* **Parameters:**
  **v** (*int*)

#### *classmethod* validate_namespace(v)

Validate the namespace string.

* **Return type:**
  `str`
* **Parameters:**
  **v** (*str*)

#### *classmethod* initialize_default_layers(v)

Initialize default cache layers if none provided.

* **Return type:**
  `List`[[`CacheLayerConfig`](#id83)]
* **Parameters:**
  **v** (*List* *[*[*CacheLayerConfig*](#id83) *]*)

#### *classmethod* validate_adaptive_ttl_range(v, info)

Validate that adaptive TTL values are reasonable.

* **Return type:**
  `int`
* **Parameters:**
  **v** (*int*)

#### *classmethod* validate_positive_ints(v)

Validate that int fields are positive.

* **Return type:**
  `int`
* **Parameters:**
  **v** (*int*)

#### *classmethod* validate_positive_float(v)

Validate that float fields are positive.

* **Return type:**
  `float`
* **Parameters:**
  **v** (*float*)

#### *classmethod* validate_signing_algorithm(v)

Validate the signing algorithm.

* **Return type:**
  `str`
* **Parameters:**
  **v** (*str*)

#### *classmethod* validate_sharding_algorithm(v)

Validate the sharding algorithm.

* **Return type:**
  `str`
* **Parameters:**
  **v** (*str*)

#### *property* full_redis_url *: str*

Constructs the full Redis URL based on the individual settings.

* **Returns:**
  The complete Redis URL including credentials if provided
* **Return type:**
  str

#### model_config *: ClassVar[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [ConfigDict][pydantic.config.ConfigDict].

## Configuration Classes

### *class* src.cache_config.CacheConfig(\*\*data)

Configuration for the CacheManager.

Provides settings for cache storage, Redis connection, and retry behavior.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **cache_dir** (*str*)
  * **cache_file** (*str*)
  * **cache_max_size** (*int*)
  * **cache_ttl** (*float*)
  * **eviction_policy** ([*EvictionPolicy*](eviction_policies.md#src.cache_config.EvictionPolicy))
  * **namespace** (*str*)
  * **use_redis** (*bool*)
  * **redis_url** (*str*)
  * **redis_port** (*int*)
  * **redis_username** (*str*)
  * **redis_password** (*str*)
  * **memory_cache_ttl** (*int*)
  * **memory_cache_enabled** (*bool*)
  * **use_layered_cache** (*bool*)
  * **cache_layers** (*List* *[*[*CacheLayerConfig*](#id83) *]*)
  * **write_through** (*bool*)
  * **read_through** (*bool*)
  * **enable_compression** (*bool*)
  * **compression_min_size** (*int*)
  * **compression_level** (*int*)
  * **disk_usage_monitoring** (*bool*)
  * **disk_usage_threshold** (*float*)
  * **disk_critical_threshold** (*float*)
  * **disk_check_interval** (*int*)
  * **disk_retention_days** (*int*)
  * **retry_attempts** (*int*)
  * **retry_delay** (*int*)
  * **environment** ([*Environment*](#id104))
  * **log_level** ([*LogLevel*](#id98))
  * **log_dir** (*str*)
  * **log_to_file** (*bool*)
  * **log_max_size** (*int*)
  * **log_backup_count** (*int*)
  * **enable_telemetry** (*bool*)
  * **telemetry_interval** (*int*)
  * **metrics_collection** (*bool*)
  * **enable_warmup** (*bool*)
  * **warmup_keys_file** (*str* *|* *None*)
  * **warmup_on_start** (*bool*)
  * **enable_adaptive_ttl** (*bool*)
  * **adaptive_ttl_min** (*int*)
  * **adaptive_ttl_max** (*int*)
  * **access_count_threshold** (*int*)
  * **adaptive_ttl_adjustment_factor** (*float*)
  * **use_distributed_locking** (*bool*)
  * **lock_timeout** (*int*)
  * **lock_retry_attempts** (*int*)
  * **lock_retry_interval** (*float*)
  * **enable_sharding** (*bool*)
  * **num_shards** (*int*)
  * **sharding_algorithm** (*str*)
  * **enable_invalidation** (*bool*)
  * **invalidation_channel** (*str*)
  * **enable_encryption** (*bool*)
  * **encryption_key** (*str* *|* *None*)
  * **encryption_salt** (*str* *|* *None*)
  * **enable_data_signing** (*bool*)
  * **signing_key** (*str* *|* *None*)
  * **signing_algorithm** (*str*)
  * **enable_access_control** (*bool*)
  * **redis_ssl** (*bool*)
  * **redis_ssl_cert_reqs** (*str* *|* *None*)
  * **redis_ssl_ca_certs** (*str* *|* *None*)
  * **redis_connection_timeout** (*float*)
  * **redis_max_connections** (*int*)
  * **use_redis_sentinel** (*bool*)
  * **sentinel_master_name** (*str*)
  * **sentinel_addresses** (*List* *[**str* *]*)
  * **disk_cache_enabled** (*bool*)
  * **disk_cache_ttl** (*float*)

#### cache_dir *: `str`*

#### cache_file *: `str`*

#### cache_max_size *: `int`*

#### cache_ttl *: `float`*

#### eviction_policy *: [`EvictionPolicy`](eviction_policies.md#src.cache_config.EvictionPolicy)*

#### namespace *: `str`*

#### use_redis *: `bool`*

#### redis_url *: `str`*

#### redis_port *: `int`*

#### redis_username *: `str`*

#### redis_password *: `str`*

#### memory_cache_ttl *: `int`*

#### memory_cache_enabled *: `bool`*

#### use_layered_cache *: `bool`*

#### cache_layers *: `List`[[`CacheLayerConfig`](#id83)]*

#### write_through *: `bool`*

#### read_through *: `bool`*

#### enable_compression *: `bool`*

#### compression_min_size *: `int`*

#### compression_level *: `int`*

#### disk_usage_monitoring *: `bool`*

#### disk_usage_threshold *: `float`*

#### disk_critical_threshold *: `float`*

#### disk_check_interval *: `int`*

#### disk_retention_days *: `int`*

#### retry_attempts *: `int`*

#### retry_delay *: `int`*

#### environment *: [`Environment`](#id104)*

#### log_level *: [`LogLevel`](#id98)*

#### log_dir *: `str`*

#### log_to_file *: `bool`*

#### log_max_size *: `int`*

#### log_backup_count *: `int`*

#### enable_telemetry *: `bool`*

#### telemetry_interval *: `int`*

#### metrics_collection *: `bool`*

#### enable_warmup *: `bool`*

#### warmup_keys_file *: `Optional`[`str`]*

#### warmup_on_start *: `bool`*

#### enable_adaptive_ttl *: `bool`*

#### adaptive_ttl_min *: `int`*

#### adaptive_ttl_max *: `int`*

#### access_count_threshold *: `int`*

#### adaptive_ttl_adjustment_factor *: `float`*

#### use_distributed_locking *: `bool`*

#### lock_timeout *: `int`*

#### lock_retry_attempts *: `int`*

#### lock_retry_interval *: `float`*

#### enable_sharding *: `bool`*

#### num_shards *: `int`*

#### sharding_algorithm *: `str`*

#### enable_invalidation *: `bool`*

#### invalidation_channel *: `str`*

#### enable_encryption *: `bool`*

#### encryption_key *: `Optional`[`str`]*

#### encryption_salt *: `Optional`[`str`]*

#### enable_data_signing *: `bool`*

#### signing_key *: `Optional`[`str`]*

#### signing_algorithm *: `str`*

#### enable_access_control *: `bool`*

#### redis_ssl *: `bool`*

#### redis_ssl_cert_reqs *: `Optional`[`str`]*

#### redis_ssl_ca_certs *: `Optional`[`str`]*

#### redis_connection_timeout *: `float`*

#### redis_max_connections *: `int`*

#### use_redis_sentinel *: `bool`*

#### sentinel_master_name *: `str`*

#### sentinel_addresses *: `List`[`str`]*

#### disk_cache_enabled *: `bool`*

#### disk_cache_ttl *: `float`*

#### *classmethod* validate_positive_int(v)

Validate that integer fields are positive.

* **Return type:**
  `int`
* **Parameters:**
  **v** (*int*)

#### *classmethod* validate_percentage(v)

Validate that threshold values are valid percentages.

* **Return type:**
  `float`
* **Parameters:**
  **v** (*float*)

#### *classmethod* validate_compression_level(v)

Validate compression level is between 1 and 9.

* **Return type:**
  `int`
* **Parameters:**
  **v** (*int*)

#### *classmethod* validate_namespace(v)

Validate the namespace string.

* **Return type:**
  `str`
* **Parameters:**
  **v** (*str*)

#### *classmethod* initialize_default_layers(v)

Initialize default cache layers if none provided.

* **Return type:**
  `List`[[`CacheLayerConfig`](#id83)]
* **Parameters:**
  **v** (*List* *[*[*CacheLayerConfig*](#id83) *]*)

#### *classmethod* validate_adaptive_ttl_range(v, info)

Validate that adaptive TTL values are reasonable.

* **Return type:**
  `int`
* **Parameters:**
  **v** (*int*)

#### *classmethod* validate_positive_ints(v)

Validate that int fields are positive.

* **Return type:**
  `int`
* **Parameters:**
  **v** (*int*)

#### *classmethod* validate_positive_float(v)

Validate that float fields are positive.

* **Return type:**
  `float`
* **Parameters:**
  **v** (*float*)

#### *classmethod* validate_signing_algorithm(v)

Validate the signing algorithm.

* **Return type:**
  `str`
* **Parameters:**
  **v** (*str*)

#### *classmethod* validate_sharding_algorithm(v)

Validate the sharding algorithm.

* **Return type:**
  `str`
* **Parameters:**
  **v** (*str*)

#### *property* full_redis_url *: str*

Constructs the full Redis URL based on the individual settings.

* **Returns:**
  The complete Redis URL including credentials if provided
* **Return type:**
  str

#### model_config *: ClassVar[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [ConfigDict][pydantic.config.ConfigDict].

### *class* src.cache_config.CacheLayerConfig(\*\*data)

Configuration for a single cache layer.

Defines the type, TTL, and other settings for a specific cache layer.

Create a new model by parsing and validating input data from keyword arguments.

Raises [ValidationError][pydantic_core.ValidationError] if the input data cannot be
validated to form a valid model.

self is explicitly positional-only to allow self as a field name.

* **Parameters:**
  * **type** ([*CacheLayerType*](#id94))
  * **ttl** (*int*)
  * **enabled** (*bool*)
  * **weight** (*int*)
  * **max_size** (*int* *|* *None*)

#### type *: [`CacheLayerType`](#id94)*

#### ttl *: `int`*

#### enabled *: `bool`*

#### weight *: `int`*

#### max_size *: `Optional`[`int`]*

#### model_config *: ClassVar[ConfigDict]* *= {}*

Configuration for the model, should be a dictionary conforming to [ConfigDict][pydantic.config.ConfigDict].

## Enumerations

### *class* src.cache_config.EvictionPolicy(\*values)

Enum defining cache eviction policies.

Available policies:
- LRU: Least Recently Used - evicts least recently accessed items first
- FIFO: First In First Out - evicts oldest items first
- LFU: Least Frequently Used - evicts least frequently accessed items

#### LRU *= 'lru'*

#### FIFO *= 'fifo'*

#### LFU *= 'lfu'*

### *class* src.cache_config.CacheLayerType(\*values)

Enum defining cache layer types.

Available types:
- MEMORY: In-memory cache (fastest, but volatile)
- REDIS: Redis cache (networked, shared across instances)
- DISK: Local disk storage via shelve (persistent, but slow)

#### MEMORY *= 'memory'*

#### REDIS *= 'redis'*

#### DISK *= 'disk'*

### *class* src.cache_config.LogLevel(\*values)

Enum defining log levels.

Available levels:
- DEBUG: Detailed debugging information
- INFO: Confirmation that things are working as expected
- WARNING: Indication that something unexpected happened
- ERROR: Due to a more serious problem, the software hasn’t been able to perform a function
- CRITICAL: A serious error indicating the program may be unable to continue running

#### DEBUG *= 'debug'*

#### INFO *= 'info'*

#### WARNING *= 'warning'*

#### ERROR *= 'error'*

#### CRITICAL *= 'critical'*

### *class* src.cache_config.Environment(\*values)

Enum defining environment types.

Available environments:
- DEV: Development environment
- TEST: Testing environment
- PROD: Production environment

#### DEV *= 'dev'*

#### TEST *= 'test'*

#### PROD *= 'prod'*

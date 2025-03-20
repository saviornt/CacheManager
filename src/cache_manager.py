import os
import logging
import logging.handlers
import functools
import uuid
import asyncio
import shutil
import time
import json
import redis.asyncio as redis
from collections import OrderedDict, Counter
from threading import RLock
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_fixed
from typing import Any, Dict, List, Optional, TypeVar, Callable, cast, TYPE_CHECKING
if TYPE_CHECKING: from redis.asyncio import Redis  # noqa: E701

from .cache_config import CacheConfig, EvictionPolicy, CacheLayerType
from .cache_layers import MemoryLayer, RedisLayer, DiskLayer
from .core.logging_setup import setup_logging, CorrelationIdFilter
from .core.exceptions import CacheSerializationError, CacheKeyError
from .core.telemetry import timed_operation
from .core.security import require_permission
from .core.invalidation import InvalidationEvent
from .core.exceptions import CacheError
from .utils.serialization import Serializer
from .utils.compression import compress_data, decompress_data
from .utils.namespacing import NamespaceManager
from .utils.disk_cache import DiskCacheManager
from .utils.initialization import CacheInitializer

# Default logger for imports and module initialization
logger = logging.getLogger(__name__)
logger.addFilter(CorrelationIdFilter())

# Initialize with a basic default config
default_config = CacheConfig()

# Create log directory if it doesn't exist
if default_config.log_to_file:
    os.makedirs(default_config.log_dir, exist_ok=True)

logger = setup_logging(default_config)

# Decorator return type
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

class CacheManager:
    """Manages caching operations with support for multiple backends.
    
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
    """
    def __init__(self, config: CacheConfig = CacheConfig()):
        """Initialize the cache manager with the given configuration.
        
        Args:
            config: Cache configuration
        """
        # Generate a correlation ID for this instance
        self._correlation_id = f"CM-{uuid.uuid4().hex[:8]}"
        self._instance_id = uuid.uuid4().hex
        
        # Store configuration
        self._config = config
        
        # Set up logging
        self._logger = setup_logging(self._config)
        self._logger.debug("Initializing CacheManager", extra={'correlation_id': self._correlation_id})
        
        # Create cache directory
        os.makedirs(self._config.cache_dir, exist_ok=True)
        
        # Initialize namespace manager
        self._namespace_manager = NamespaceManager(config.namespace)
        
        # Initialize disk cache manager
        self._disk_cache_manager = DiskCacheManager(
            cache_dir=self._config.cache_dir,
            cache_file=self._config.cache_file,
            namespace=self._config.namespace,
            correlation_id=self._correlation_id
        )
        
        # Initialize shelve file path
        self.shelve_file = self._disk_cache_manager.shelve_file
        
        # Initialize stats counters
        self._stats = {
            "hits": 0,
            "misses": 0, 
            "sets": 0,
            "errors": 0,
            "layer_hits": {},  # Will be populated with string keys as needed
            "layer_sets": 0,
            "layer_deletes": 0,
            "evictions": 0,
            "disk_usage": 0
        }
        
        # Initialize layer hit counters if layered cache is enabled
        if self._config.use_layered_cache:
            for layer in self._config.cache_layers:
                if layer.enabled:
                    self._stats["layer_hits"][str(layer.type)] = 0
        
        # Set up Redis and other configurations
        self._use_redis = self._config.use_redis and redis is not None
        
        # Use appropriate data structures based on eviction policy
        if self._config.eviction_policy == EvictionPolicy.LRU:
            # For LRU, we use OrderedDict to track access order
            self.cached_keys = OrderedDict()
        elif self._config.eviction_policy == EvictionPolicy.FIFO:
            # For FIFO, we use OrderedDict without reordering on access
            self.cached_keys = OrderedDict()
        elif self._config.eviction_policy == EvictionPolicy.LFU:
            # For LFU, we use OrderedDict for consistent iteration and Counter for frequencies
            self.cached_keys = OrderedDict()
            self.access_frequencies = Counter()
        
        # Locks for thread safety
        self._keys_lock = RLock()
        self._stats_lock = RLock()
        self._cleanup_in_progress = False
        
        # Redis client is lazily initialized
        self._redis = None
        
        # Circuit breakers for different operations
        self._breakers = {}
        
        # Initialize tasks tracking
        self._tasks = set()
        self._disk_monitor_task = None
        self._warmup_task = None
        self._telemetry_task = None
        
        # Use initializer for cache layers and core components
        initializer = CacheInitializer(self._config, self._correlation_id)
        
        # Setup cache layers
        layers_info = initializer.setup_cache_layers()
        self._cache_layers = layers_info["cache_layers"]
        self._primary_layer = layers_info["primary_layer"]
        self._primary_layer_type = layers_info["primary_layer_type"]
        self._layer_order = layers_info["layer_order"]
        
        self._logger.debug(
            f"CacheManager initialized with config: "
            f"redis={self._use_redis}, "
            f"memory_cache={self._config.memory_cache_enabled}, "
            f"eviction_policy={self._config.eviction_policy}, "
            f"namespace={self._config.namespace}, "
            f"layered_cache={self._config.use_layered_cache}, "
            f"compression={self._config.enable_compression}",
            extra={'correlation_id': self._correlation_id}
        )
        
        # Start disk monitoring if enabled
        if self._config.disk_usage_monitoring:
            self._setup_disk_monitoring()
        
        # Initialize core components after Redis client is available
        core_components = initializer.setup_core_components()
        
        # Set components 
        self._telemetry = core_components.get("telemetry")
        self._adaptive_ttl = core_components.get("adaptive_ttl")
        self._cache_warmup = core_components.get("cache_warmup")
        self._encryptor = core_components.get("encryptor")
        self._data_signer = core_components.get("data_signer")
        self._access_control = core_components.get("access_control")
        
        # Default user
        self._current_user = {'id': 'system', 'roles': ['admin']}
        
        # Initialize distributed components if Redis is available
        if self._use_redis:
            # Get Redis client (will be initialized lazily when needed)
            self._create_task(self._initialize_distributed_components())
            
        # Start other async tasks
        if self._config.enable_warmup and self._config.warmup_on_start:
            self._warmup_task = self._create_task(self._cache_warmup.warmup(self))
            
    async def _initialize_distributed_components(self):
        """Initialize components that need a Redis client."""
        try:
            # Get Redis client
            redis_client = await self._get_redis_client()
            
            # Initialize core components that require Redis
            initializer = CacheInitializer(self._config, self._correlation_id)
            distributed_components = initializer.setup_core_components(redis_client)
            
            # Set distributed components
            self._invalidation_manager = distributed_components.get("invalidation_manager")
            self._shard_manager = distributed_components.get("shard_manager")
            
            # Start invalidation manager
            if self._invalidation_manager and self._invalidation_manager.enabled:
                await self._start_invalidation_manager()
        except Exception as e:
            self._logger.error(f"Failed to initialize distributed components: {e}", 
                               extra={"correlation_id": self._correlation_id})
            
    async def _start_invalidation_manager(self):
        """Start the invalidation manager and register handlers."""
        try:
            await self._invalidation_manager.start()
            
            # Register invalidation handlers
            async def handle_key_invalidation(data: Dict[str, Any]) -> None:
                """Handle invalidation for a specific key."""
                key = data.get('key')
                if key:
                    # Delete from all cache layers
                    for layer in self._cache_layers.values():
                        await layer.delete(self._namespace_key(key))
            
            async def handle_pattern_invalidation(data: Dict[str, Any]) -> None:
                """Handle invalidation for a pattern (multiple keys)."""
                pattern = data.get('pattern')
                if pattern:
                    # Placeholder for pattern invalidation
                    pass
            
            async def handle_namespace_invalidation(data: Dict[str, Any]) -> None:
                """Handle invalidation for an entire namespace."""
                namespace = data.get('namespace')
                if namespace == self._config.namespace:
                    # Clear all cache layers for this namespace
                    await self.clear()
            
            self._invalidation_manager.add_callback(InvalidationEvent.KEY, handle_key_invalidation)
            self._invalidation_manager.add_callback(InvalidationEvent.PATTERN, handle_pattern_invalidation)
            self._invalidation_manager.add_callback(InvalidationEvent.NAMESPACE, handle_namespace_invalidation)
            
            self._logger.debug("Invalidation manager started", 
                              extra={"correlation_id": self._correlation_id})
        except Exception as e:
            self._logger.error(f"Failed to start invalidation manager: {e}", 
                               extra={"correlation_id": self._correlation_id})

    def _create_task(self, coro) -> asyncio.Task:
        """Create and track an asyncio task.
        
        Args:
            coro: The coroutine to run as a task
            
        Returns:
            asyncio.Task: The created task
        """
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def _setup_cache_layers(self) -> None:
        """Set up cache layers based on configuration.
        
        Initializes memory, redis, or disk layers as specified in config.
        """
        # Initialize cache layers based on configuration
        self._cache_layers = {}
        
        # Always add memory cache if enabled
        if self._config.memory_cache_enabled:
            self._cache_layers[CacheLayerType.MEMORY] = MemoryLayer(
                namespace=self._config.namespace,
                ttl=self._config.memory_cache_ttl,
                max_size=self._config.cache_max_size,
                eviction_policy=self._config.eviction_policy
            )
            
            # Use memory as primary layer by default
            if not self._primary_layer:
                self._primary_layer = self._cache_layers[CacheLayerType.MEMORY]
                self._primary_layer_type = CacheLayerType.MEMORY
        
        # Add disk cache if enabled
        if self._config.disk_cache_enabled:
            # Add namespace to shelve file to isolate different namespaces
            namespace_suffix = (
                f"_{self._config.namespace}" 
                if self._config.namespace != "default" 
                else ""
            )
            
            cache_file = os.path.join(
                self._config.cache_dir, 
                f"{os.path.splitext(self._config.cache_file)[0]}{namespace_suffix}.db"
            )
            
            self._cache_layers[CacheLayerType.DISK] = DiskLayer(
                namespace=self._config.namespace,
                ttl=self._config.disk_cache_ttl,
                cache_dir=self._config.cache_dir,
                cache_file=cache_file
            )
            
            # Use disk as primary layer if memory is disabled
            if not self._primary_layer:
                self._primary_layer = self._cache_layers[CacheLayerType.DISK]
                self._primary_layer_type = CacheLayerType.DISK
        
        # Add Redis cache if enabled
        if self._config.use_redis:
            # Try to initialize Redis
            try:
                redis_layer = RedisLayer(
                    namespace=self._config.namespace,
                    ttl=self._config.redis_ttl,
                    host=self._config.redis_host,
                    port=self._config.redis_port,
                    db=self._config.redis_db,
                    password=self._config.redis_password
                )
                self._cache_layers[CacheLayerType.REDIS] = redis_layer
                
                # Use Redis as primary layer if specifically configured
                if getattr(self._config, 'primary_layer', None) == CacheLayerType.REDIS:
                    self._primary_layer = self._cache_layers[CacheLayerType.REDIS]
                    self._primary_layer_type = CacheLayerType.REDIS
            except Exception as e:
                self._logger.error(f"Failed to initialize Redis layer: {e}")
                
        # If no layers were enabled, add memory layer as fallback
        if not self._cache_layers:
            self._logger.warning("No cache layers were enabled; adding memory layer as fallback")
            self._cache_layers[CacheLayerType.MEMORY] = MemoryLayer(
                namespace=self._config.namespace,
                ttl=self._config.memory_cache_ttl
            )
            self._primary_layer = self._cache_layers[CacheLayerType.MEMORY]
            self._primary_layer_type = CacheLayerType.MEMORY
            
        # Set up layer order for layered caching
        if self._config.use_layered_cache:
            self._layer_order = [layer.type for layer in self._config.cache_layers 
                                 if layer.enabled and layer.type in self._cache_layers]
            
            # Set primary layer based on config
            if self._layer_order:
                self._primary_layer_type = self._layer_order[0]
                self._primary_layer = self._cache_layers[self._primary_layer_type]
        
        self._logger.debug(
            f"Cache layers initialized: "
            f"memory={CacheLayerType.MEMORY in self._cache_layers}, "
            f"redis={CacheLayerType.REDIS in self._cache_layers}, "
            f"disk={CacheLayerType.DISK in self._cache_layers}, "
            f"primary={self._primary_layer_type}",
            extra={"correlation_id": self._correlation_id}
        )

    def _namespace_key(self, key: str) -> str:
        """Add namespace prefix to a key.
        
        Args:
            key: The original key
            
        Returns:
            str: The namespaced key
        """
        return self._namespace_manager.namespace_key(key)
    
    def _remove_namespace(self, namespaced_key: str) -> str:
        """Remove namespace prefix from a key.
        
        Args:
            namespaced_key: The namespaced key
            
        Returns:
            str: The original key without namespace
        """
        return self._namespace_manager.remove_namespace(namespaced_key)
    
    def _namespace_keys_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add namespace prefix to all keys in a dictionary.
        
        Args:
            data: Dictionary with original keys
            
        Returns:
            Dict[str, Any]: Dictionary with namespaced keys
        """
        return self._namespace_manager.namespace_keys_dict(data)
    
    def _remove_namespace_from_keys_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove namespace prefix from all keys in a dictionary.
        
        Args:
            data: Dictionary with namespaced keys
            
        Returns:
            Dict[str, Any]: Dictionary with original keys
        """
        return self._namespace_manager.remove_namespace_from_keys_dict(data)

    async def _get_redis_client(self) -> 'Redis':
        """Get or create a Redis client connection pool.
        
        Returns:
            Redis: Redis client instance with connection pooling
            
        Raises:
            CacheConnectionError: If Redis client cannot be created
        """
        if self._redis is not None:
            return self._redis
            
        if not self._config.use_redis:
            raise CacheError("Redis is not enabled in configuration")
            
        try:
            import redis.asyncio as aioredis
            
            # Use the full Redis URL with all settings
            self._redis = aioredis.from_url(
                self._config.full_redis_url,
                socket_timeout=self._config.redis_connection_timeout,
                socket_connect_timeout=self._config.redis_connection_timeout,
                ssl=self._config.redis_ssl,
                ssl_cert_reqs=self._config.redis_ssl_cert_reqs,
                ssl_ca_certs=self._config.redis_ssl_ca_certs,
                max_connections=self._config.redis_max_connections
            )
            
            # Test the connection
            try:
                await self._redis.ping()
                self._logger.debug(
                    "Redis connection established", 
                    extra={"correlation_id": self._correlation_id}
                )
            except Exception as e:
                self._redis = None
                raise CacheError(f"Redis connection test failed: {e}") from e
                
            return self._redis
            
        except ImportError as e:
            self._logger.error(
                "Redis package not installed", 
                extra={"correlation_id": self._correlation_id}
            )
            raise CacheError("Redis package not installed") from e
        except Exception as e:
            self._logger.error(
                f"Failed to initialize Redis client: {e}", 
                extra={"correlation_id": self._correlation_id}
            )
            raise CacheError(f"Failed to initialize Redis client: {e}") from e

    def _evict_if_needed(self) -> None:
        """Evict cache entries if max size has been reached.
        
        Applies the configured eviction policy to remove entries.
        """
        with self._keys_lock:
            # Check if cache is full
            if len(self.cached_keys) > self._config.cache_max_size:
                self._logger.debug("Cache is full, evicting items")
                
                # Evict items until we're under the limit
                while len(self.cached_keys) > self._config.cache_max_size:
                    # Choose eviction strategy
                    if self._config.eviction_policy == EvictionPolicy.LRU:
                        # LRU - Evict the least recently used item
                        old_key, _ = self.cached_keys.popitem(last=False)
                    elif self._config.eviction_policy == EvictionPolicy.FIFO:
                        # FIFO - Evict the first item that was added
                        old_key, _ = self.cached_keys.popitem(last=False)
                    elif self._config.eviction_policy == EvictionPolicy.LFU:
                        # LFU - Evict the least frequently used item
                        # Find key with lowest access count
                        access_counts = self.access_frequencies
                        old_key = min(self.cached_keys.keys(), key=lambda k: access_counts.get(k, 0))
                        # Remove it from cached_keys and access_counts
                        del self.cached_keys[old_key]
                        if old_key in access_counts:
                            del access_counts[old_key]
                    else:
                        # Default to LRU
                        old_key, _ = self.cached_keys.popitem(last=False)
                    
                    self._logger.debug(
                        f"Evicting key: {old_key} from cache using {self._config.eviction_policy} policy",
                        extra={"correlation_id": self._correlation_id}
                    )
                    self._stats["evictions"] += 1

    def _check_ttl(self, key: str, timestamp: float) -> bool:
        """Check if a cache entry is still valid based on TTL.
        
        Args:
            key: Cache key to check
            timestamp: Timestamp when the entry was stored
            
        Returns:
            bool: True if entry is still valid, False if expired
        """
        now = datetime.now()
        if now > timestamp + timedelta(seconds=self._config.memory_cache_ttl):
            self._logger.debug(f"Key {key} has expired", extra={"correlation_id": self._correlation_id})
            return True
        return False

    def _setup_disk_monitoring(self) -> None:
        """Set up disk usage monitoring if enabled in config."""
        if self._config.disk_usage_monitoring:
            self._disk_monitor_task = self._create_task(self._monitor_disk_usage())
            self._logger.debug("Disk usage monitoring started", extra={"correlation_id": self._correlation_id})

    async def _monitor_disk_usage(self) -> None:
        """Periodically monitor disk usage and trigger cleanup if needed.
        
        This is a background task that runs at regular intervals.
        """
        self._logger.info("Starting disk usage monitoring", extra={"correlation_id": self._correlation_id})
        
        try:
            while True:
                # Check disk usage
                disk_usage = self._disk_cache_manager.get_disk_usage()
                
                # Calculate percentage used
                percent_used = disk_usage
                
                self._logger.debug(
                    f"Disk usage: {percent_used:.1f}%", 
                    extra={"correlation_id": self._correlation_id}
                )
                
                # Critical threshold - initiate emergency cleanup
                if percent_used >= self._config.disk_critical_threshold:
                    self._logger.warning(
                        f"Disk usage critical at {percent_used:.1f}% "
                        f"(threshold: {self._config.disk_critical_threshold}%). "
                        f"Performing emergency cleanup.",
                        extra={"correlation_id": self._correlation_id}
                    )
                    await self._cleanup_disk_cache(aggressive=True)
                    
                # Warning threshold - initiate normal cleanup
                elif percent_used >= self._config.disk_usage_threshold:
                    self._logger.info(
                        f"Disk usage high at {percent_used:.1f}% "
                        f"(threshold: {self._config.disk_usage_threshold}%). "
                        f"Performing cleanup.",
                        extra={"correlation_id": self._correlation_id}
                    )
                    await self._cleanup_disk_cache(aggressive=False)
                    
                # Wait for next check interval
                await asyncio.sleep(self._config.disk_check_interval)
                
        except asyncio.CancelledError:
            self._logger.info("Disk usage monitoring stopped", extra={"correlation_id": self._correlation_id})
            raise

    async def _cleanup_disk_cache(self, aggressive: bool = False) -> int:
        """Clean up the disk cache by removing oldest entries.
        
        Args:
            aggressive: If True, perform more aggressive cleanup
            
        Returns:
            int: Number of items removed
        """
        return await self._disk_cache_manager.clean_disk_cache(
            retention_days=self._config.disk_retention_days,
            aggressive=aggressive
        )

    async def _clean_disk_cache(self, aggressive: bool = False) -> int:
        """Alias for _cleanup_disk_cache for backward compatibility.
        
        Args:
            aggressive: If True, perform more aggressive cleanup
            
        Returns:
            int: Number of items removed
        """
        return await self._cleanup_disk_cache(aggressive=aggressive)
        
    async def _compact_cache(self) -> None:
        """Compact the disk cache to reclaim space.
        
        This removes fragmentation and frees up disk space.
        """
        await self._disk_cache_manager.compact_cache()

    def _serialize(self, value: Any) -> bytes:
        """Serialize a value for storage.
        
        Serializes the value with msgpack, and optionally compresses, encrypts, and signs it.
        
        Args:
            value: The value to serialize
            
        Returns:
            bytes: The serialized value
            
        Raises:
            CacheSerializationError: If serialization fails
        """
        # Create a serializer with the current configuration
        serializer = Serializer(
            enable_compression=getattr(self._config, 'enable_compression', False),
            compression_min_size=getattr(self._config, 'compression_min_size', 1024),
            compression_level=getattr(self._config, 'compression_level', 6),
            encryptor=getattr(self, '_encryptor', None),
            data_signer=getattr(self, '_data_signer', None),
            stats=self._stats,
            correlation_id=self._correlation_id
        )
        
        try:
            return serializer.serialize(value)
        except CacheSerializationError:
            # Re-raise the exception which is already properly formatted
            raise
        except Exception as e:
            self._logger.error(
                f"Failed to serialize value: {e}", 
                extra={"correlation_id": self._correlation_id}
            )
            self._stats["errors"] += 1
            raise CacheSerializationError(f"Failed to serialize value: {e}") from e

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize a value from storage.
        
        Deserializes a value previously serialized with _serialize.
        
        Args:
            data: The data to deserialize
            
        Returns:
            The deserialized value
            
        Raises:
            CacheSerializationError: If deserialization fails
        """
        # Create a serializer with the current configuration
        serializer = Serializer(
            enable_compression=getattr(self._config, 'enable_compression', False),
            compression_min_size=getattr(self._config, 'compression_min_size', 1024),
            compression_level=getattr(self._config, 'compression_level', 6),
            encryptor=getattr(self, '_encryptor', None),
            data_signer=getattr(self, '_data_signer', None),
            stats=self._stats,
            correlation_id=self._correlation_id
        )
        
        try:
            return serializer.deserialize(data)
        except CacheSerializationError:
            # Re-raise the exception which is already properly formatted
            raise
        except Exception as e:
            self._logger.error(
                f"Failed to deserialize data: {e}", 
                extra={"correlation_id": self._correlation_id}
            )
            self._stats["errors"] += 1
            raise CacheSerializationError(f"Failed to deserialize data: {e}") from e

    def _decode_complex_types(self, code: str, data: Any) -> Any:
        """Decode complex types like datetimes from serialized form.
        
        Args:
            code: Type code from serialization
            data: Serialized data
            
        Returns:
            Any: Deserialized data with proper Python types
        """
        # Currently we don't have custom types, but this allows for future extension
        return data

    @retry(stop=stop_after_attempt(CacheConfig().retry_attempts), 
           wait=wait_fixed(CacheConfig().retry_delay))
    @timed_operation("get")
    @require_permission("read")
    async def get(self, key: str) -> Any:
        """Get a value from the cache.
        
        Args:
            key: The cache key
            
        Returns:
            Any: The cached value or None if not found
            
        Raises:
            CacheError: If there's an error accessing the cache
        """
        # Record access for adaptive TTL
        if hasattr(self, '_adaptive_ttl') and self._adaptive_ttl.enabled:
            self._adaptive_ttl.record_access(key)
        
        if not key:
            raise CacheKeyError("Cache key cannot be empty")
            
        log_extra = {'correlation_id': self._correlation_id}
        logger.debug(f"Getting key: {key}", extra=log_extra)
        
        try:
            if getattr(self._config, 'use_layered_cache', False):
                # Try each cache layer in order
                for layer_config in self._config.cache_layers:
                    if not layer_config.enabled:
                        continue
                        
                    layer_type = layer_config.type
                    if layer_type not in self._cache_layers:
                        continue
                        
                    layer = self._cache_layers[layer_type]
                    found, value = await layer.get(key)
                    
                    if found:
                        self._stats["hits"] += 1
                        layer_type_str = str(layer_type)
                        if layer_type_str in self._stats["layer_hits"]:
                            self._stats["layer_hits"][layer_type_str] += 1
                        
                        # Record hit in telemetry
                        if self._telemetry and self._telemetry.enabled:
                            self._telemetry._counters['cache.hit'] += 1
                            
                        logger.debug(
                            f"Cache hit for key: {key} in layer: {layer_type}", 
                            extra=log_extra
                        )
                        
                        # If found in any layer except the first, and read-through is enabled,
                        # populate previous layers
                        if (getattr(self._config, 'read_through', False) and 
                                layer_type != self._config.cache_layers[0].type):
                            # Propagate to higher-priority layers
                            await self._propagate_to_higher_layers(key, value, layer_type)
                        
                        # Decompress value if compression is enabled
                        if getattr(self._config, 'enable_compression', False):
                            value = decompress_data(value, self._config)
                            
                        return value
                
                # Not found in any layer
                self._stats["misses"] += 1
                
                # Record miss in telemetry
                if self._telemetry and self._telemetry.enabled:
                    self._telemetry._counters['cache.miss'] += 1
                    
                logger.debug(f"Cache miss for key: {key}", extra=log_extra)
                return None
            else:
                # For backward compatibility: use the first available layer
                for layer in self._cache_layers.values():
                    # Get the layer type for this layer
                    layer_type = getattr(layer, 'type', 'UNKNOWN')
                    found, value = await layer.get(key)
                    if found:
                        self._stats["hits"] += 1
                        
                        # Record hit in telemetry
                        if self._telemetry and self._telemetry.enabled:
                            self._telemetry._counters['cache.hit'] += 1
                            
                        logger.debug(f"Cache hit for key: {key} in layer: {layer_type}", extra=log_extra)
                        
                        # Update the recent keys tracker for LRU/access tracking
                        if hasattr(self, '_recent_keys'):
                            self._recent_keys[key] = time.time()
                            
                        # Decompress value if compression is enabled
                        if getattr(self._config, 'enable_compression', False):
                            value = decompress_data(value, self._config)
                            
                        return value
                
                self._stats["misses"] += 1
                
                # Record miss in telemetry
                if self._telemetry and self._telemetry.enabled:
                    self._telemetry._counters['cache.miss'] += 1
                    
                logger.debug(f"Cache miss for key: {key}", extra=log_extra)
                return None
        except CacheError:
            # Record error in telemetry
            if self._telemetry and self._telemetry.enabled:
                self._telemetry._counters['cache.error'] += 1
            # Re-raise CacheError to allow the retry decorator to catch it
            raise
        except Exception as e:
            logger.error(f"Error getting key {key}: {str(e)}")
            
            # Record error in telemetry
            if self._telemetry and self._telemetry.enabled:
                self._telemetry._counters['cache.error'] += 1
                
            # Convert to CacheError and re-raise for retry
            cache_error = CacheError(f"Error getting key {key}: {str(e)}")
            raise cache_error from e

    @retry(stop=stop_after_attempt(CacheConfig().retry_attempts), 
           wait=wait_fixed(CacheConfig().retry_delay))
    @timed_operation("set")
    @require_permission("write")
    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to store
            ttl: Time to live in seconds (overrides the default)
            
        Returns:
            bool: True if set successfully, False otherwise
            
        Raises:
            CacheError: If there's an error setting the value in cache
        """
        if not key:
            logger.error("Cache key cannot be empty")
            return False
            
        logger.debug(f"Setting key: {key}")
        
        # Record statistics
        self._stats["sets"] += 1
        
        # Check access control if enabled
        if self._access_control and not self._access_control.check_access(self._current_user, key, "write"):
            logger.warning(f"Access denied for set operation on key: {key}")
            return False
            
        # Use default TTL if none provided
        if ttl is None:
            # Use a default TTL of 3600 seconds (1 hour) if not specified in config
            ttl = getattr(self._config, 'default_ttl', 3600)
            
        # If adaptive TTL is enabled, adjust TTL based on access patterns
        if self._adaptive_ttl and self._adaptive_ttl.enabled:
            ttl = self._adaptive_ttl.adjust_ttl(key, int(ttl))
            self._adaptive_ttl.record_access(key)
        
        success = False
        
        try:
            # Compress value if compression is enabled
            if getattr(self._config, 'enable_compression', False) and isinstance(value, (str, bytes)):
                value = compress_data(value, self._config)
            
            # Handle layered cache if enabled
            if getattr(self._config, 'use_layered_cache', False):
                for i, layer_type in enumerate(self._layer_order):
                    if layer_type not in self._cache_layers:
                        continue
                        
                    # If write-through is disabled and this is not the first layer, skip
                    if i > 0 and not getattr(self._config, 'write_through', True):
                        break
                        
                    layer = self._cache_layers[layer_type]
                    layer_success = await self._set_in_layer(layer, key, value, ttl)
                    if layer_type == self._primary_layer_type:
                        success = layer_success
                    self._stats["layer_sets"] += 1
            else:
                # Just use the primary layer
                success = await self._set_in_layer(self._primary_layer, key, value, ttl)
            
            # Update cache size gauge if telemetry is enabled
            if self._telemetry and self._telemetry.enabled:
                # Estimate cache size
                cache_size = len(self._primary_layer) if hasattr(self._primary_layer, '__len__') else 0
                self._telemetry.record_gauge('cache.size', cache_size)
                
            # Publish invalidation if cross-node invalidation is enabled
            if getattr(self._config, 'cross_node_invalidation', False) and self._redis_client:
                await self._publish_invalidation(key)
                
        except CacheError:
            # Record error in telemetry
            if self._telemetry:
                self._telemetry._counters['cache.error'] += 1
            # Re-raise to allow retry
            raise
        except Exception as e:
            logger.error(f"Error setting key {key}: {str(e)}")
            if self._telemetry:
                self._telemetry._counters['cache.error'] += 1
            # Convert to CacheError and re-raise for retry
            cache_error = CacheError(f"Error setting key {key}: {str(e)}")
            raise cache_error from e
                
        return success

    @retry(stop=stop_after_attempt(CacheConfig().retry_attempts), 
           wait=wait_fixed(CacheConfig().retry_delay))
    async def delete(self, key: str) -> bool:
        """Delete a value from the cache.
        
        Args:
            key: The cache key to delete
            
        Returns:
            bool: True if the key was deleted, False if it did not exist
            
        Raises:
            CacheConnectionError: If there's an error connecting to the cache backend
            CacheKeyError: If the key is invalid
        """
        if not key:
            raise CacheKeyError("Cache key cannot be empty")
            
        log_extra = {'correlation_id': self._correlation_id}
        logger.debug(f"Deleting key: {key}", extra=log_extra)
        
        deleted = False
        
        # Delete from all layers
        for layer in self._cache_layers.values():
            layer_deleted = await layer.delete(key)
            deleted = deleted or layer_deleted
            
        return deleted

    async def clear(self) -> None:
        """Clear all cache entries from all active layers.
        
        Returns:
            None
        """
        log_extra = {'correlation_id': self._correlation_id}
        logger.debug("Clearing all cache keys", extra=log_extra)
        
        # Clear each layer
        for layer_type, layer in self._cache_layers.items():
            try:
                await layer.clear()
                logger.debug(f"Cleared {layer_type} layer", extra=log_extra)
            except Exception as e:
                logger.error(f"Error clearing {layer_type} layer: {e}", extra=log_extra)
        
        # Reset statistics
        for key in self._stats:
            if isinstance(self._stats[key], dict):
                for subkey in self._stats[key]:
                    self._stats[key][subkey] = 0
            else:
                self._stats[key] = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dict[str, Any]: Dictionary with cache statistics
        """
        stats = self._stats.copy()
        
        # Calculate hit rate
        total_requests = stats["hits"] + stats["misses"]
        if total_requests > 0:
            stats["hit_rate"] = stats["hits"] / total_requests
        else:
            stats["hit_rate"] = 0.0
            
        # Add current size information if using the memory layer
        if CacheLayerType.MEMORY in self._cache_layers:
            memory_layer = self._cache_layers[CacheLayerType.MEMORY]
            if hasattr(memory_layer, '_cache'):
                stats["memory_size"] = len(memory_layer._cache)
        
        # Add disk usage information if monitoring is enabled
        if self._config.disk_usage_monitoring:
            stats["disk_usage_percent"] = self._get_disk_layer_usage()
        
        return stats

    def cached(self, ttl: Optional[int] = None, key_func: Optional[Callable[..., str]] = None) -> Callable[[F], F]:
        """Decorator to cache function results.
        
        Args:
            ttl: Time to live in seconds (overrides the default)
            key_func: Optional function to generate custom cache keys
            
        Returns:
            Decorator function
        """
        def decorator(func: F) -> F:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Generate cache key from function name and arguments
                if key_func:
                    # Use custom key function if provided
                    custom_key = key_func(*args, **kwargs)
                    key = f"{func.__module__}:{func.__qualname__}:{custom_key}"
                else:
                    # Default key generation
                    key_parts = [
                        func.__module__,
                        func.__qualname__,
                    ]
                    key_parts.extend(str(arg) for arg in args)
                    key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                    key = ":".join(key_parts)
                
                # Try to get from cache first
                cached_value = await self.get(key)
                if cached_value is not None:
                    return cached_value
                    
                # Not in cache, execute function
                result = await func(*args, **kwargs)
                
                # Store in cache
                await self.set(key, result, ttl=ttl)
                
                return result
                
            # Store original function and key_func for invalidation
            wrapper.__cached_original__ = func
            wrapper.__key_func__ = key_func
                
            return cast(F, wrapper)
        return decorator

    async def invalidate_cached(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
        """Invalidate a cached function result for specific arguments.
        
        Args:
            func: The decorated function whose cache to invalidate
            *args: The function arguments
            **kwargs: The function keyword arguments
            
        Returns:
            bool: True if invalidation was successful, False otherwise
            
        Raises:
            AttributeError: If the function is not decorated with @cached
        """
        if hasattr(func, '__cached_original__'):
            # Get the original function
            original_func = func.__cached_original__
            key_func = getattr(func, '__key_func__', None)
            
            if key_func:
                # Use custom key function if provided
                custom_key = key_func(*args, **kwargs)
                key = f"{original_func.__module__}:{original_func.__qualname__}:{custom_key}"
            else:
                # Default key generation (must match decorator implementation)
                key_parts = [
                    original_func.__module__,
                    original_func.__qualname__,
                ]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                key = ":".join(key_parts)
                
            # Delete the key from cache
            return await self.delete(key)
        else:
            # If this is an original function (not wrapped), try to find its wrapper
            if hasattr(func, '__qualname__'):
                # Try direct invalidation with module and qualname
                key_parts = [
                    func.__module__,
                    func.__qualname__,
                ]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                key = ":".join(key_parts)
                return await self.delete(key)
            
            raise AttributeError("Function is not decorated with @cached")

    @retry(stop=stop_after_attempt(CacheConfig().retry_attempts), 
           wait=wait_fixed(CacheConfig().retry_delay))
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from the cache at once.
        
        Args:
            keys: List of cache keys to retrieve
            
        Returns:
            Dict[str, Any]: Dictionary mapping keys to their values (only existing keys)
            
        Raises:
            CacheConnectionError: If there's an error connecting to the cache backend
            CacheSerializationError: If there's an error deserializing the data
        """
        if not keys:
            return {}
            
        log_extra = {'correlation_id': self._correlation_id}
        logger.debug(f"Getting {len(keys)} keys with get_many", extra=log_extra)
        
        result = {}
        
        if self._config.use_layered_cache:
            # Get from each layer, filling in missing keys
            remaining_keys = set(keys)
            
            for layer_config in self._config.cache_layers:
                if not layer_config.enabled or not remaining_keys:
                    continue
                    
                layer_type = layer_config.type
                if layer_type not in self._cache_layers:
                    continue
                    
                layer = self._cache_layers[layer_type]
                layer_results = await layer.get_many(list(remaining_keys))
                
                # Add to result and track which keys were found
                for key, value in layer_results.items():
                    result[key] = value
                    remaining_keys.remove(key)
                    self._stats["hits"] += 1
                    layer_type_str = str(layer_type)
                    if layer_type_str in self._stats["layer_hits"]:
                        self._stats["layer_hits"][layer_type_str] += 1
                
                # If read-through is enabled, populate previous layers with found values
                if (self._config.read_through and 
                        layer_results and 
                        layer_type != self._config.cache_layers[0].type):
                    # For each key found in this layer, populate previous layers
                    for prev_layer_config in self._config.cache_layers:
                        if not prev_layer_config.enabled:
                            continue
                            
                        prev_layer_type = prev_layer_config.type
                        if prev_layer_type == layer_type:
                            break
                            
                        if prev_layer_type in self._cache_layers:
                            prev_layer = self._cache_layers[prev_layer_type]
                            await prev_layer.set_many(layer_results)
            
            # Count misses
            self._stats["misses"] += len(remaining_keys)
                
        else:
            # For backward compatibility, try each layer in order
            remaining_keys = set(keys)
            
            for layer in self._cache_layers.values():
                if not remaining_keys:
                    break
                    
                layer_results = await layer.get_many(list(remaining_keys))
                
                # Add to result and track which keys were found
                for key, value in layer_results.items():
                    result[key] = value
                    remaining_keys.remove(key)
                    self._stats["hits"] += 1
                    # Get layer type for this layer
                    current_layer_type = getattr(layer, 'type', 'UNKNOWN')
                    layer_type_str = str(current_layer_type)
                    if layer_type_str in self._stats["layer_hits"]:
                        self._stats["layer_hits"][layer_type_str] += 1
            
            # Count misses
            self._stats["misses"] += len(remaining_keys)
        
        return result

    @retry(stop=stop_after_attempt(CacheConfig().retry_attempts), 
           wait=wait_fixed(CacheConfig().retry_delay))
    async def set_many(self, key_values: Dict[str, Any], expiration: Optional[int] = None):
        """Set multiple values in the cache at once.
        
        Args:
            key_values: Dictionary mapping keys to values
            expiration: Optional expiration time in seconds
            
        Raises:
            CacheConnectionError: If there's an error connecting to the cache backend
            CacheSerializationError: If there's an error serializing the data
        """
        if not key_values:
            return
            
        log_extra = {'correlation_id': self._correlation_id}
        logger.debug(f"Setting {len(key_values)} keys with set_many", extra=log_extra)
        
        self._stats["sets"] += len(key_values)
        
        if self._config.use_layered_cache:
            # Set in each layer as configured
            for i, layer_config in enumerate(self._config.cache_layers):
                if not layer_config.enabled:
                    continue
                    
                layer_type = layer_config.type
                if layer_type not in self._cache_layers:
                    continue
                    
                # If write-through is disabled and this is not the first layer, skip
                if i > 0 and not self._config.write_through:
                    break
                    
                layer = self._cache_layers[layer_type]
                ttl = expiration or layer_config.ttl
                await layer.set_many(key_values, ttl)
        else:
            # For backward compatibility: use all available layers
            for layer in self._cache_layers.values():
                await layer.set_many(key_values, expiration)

    # Async context management to ensure proper cleanup
    async def __aenter__(self) -> 'CacheManager':
        """Enter async context manager.
        
        Returns:
            CacheManager: Returns self for context manager
        """
        return self

    async def __aexit__(self, exc_type: Optional[type], exc: Optional[Exception], tb: Optional[Any]) -> None:
        """Exit async context manager and clean up resources."""
        await self.close()

    async def close(self) -> None:
        """Close the cache manager and release all resources."""
        self._logger.debug("Closing CacheManager and releasing resources", extra={"correlation_id": self._correlation_id})
        
        # Cancel all tracked tasks
        tasks_to_cancel = list(self._tasks)
        for task in tasks_to_cancel:
            if not task.done():
                task.cancel()
        
        # Specifically handle main background tasks
        for task_name, task in [
            ("disk_monitor_task", self._disk_monitor_task),
            ("warmup_task", self._warmup_task),
            ("telemetry_task", self._telemetry_task)
        ]:
            if task and not task.done():
                self._logger.debug(f"Cancelling {task_name}", extra={"correlation_id": self._correlation_id})
                task.cancel()
                try:
                    await asyncio.shield(asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=2))
                except (asyncio.CancelledError, asyncio.TimeoutError) as e:
                    self._logger.debug(f"{task_name} cancellation: {str(e)}", extra={"correlation_id": self._correlation_id})
        
        # Wait for all tasks to complete
        if self._tasks:
            self._logger.debug(f"Waiting for {len(self._tasks)} tasks to complete", extra={"correlation_id": self._correlation_id})
            try:
                await asyncio.wait_for(asyncio.gather(*self._tasks, return_exceptions=True), timeout=5)
            except asyncio.TimeoutError:
                self._logger.warning("Timeout waiting for tasks to complete", extra={"correlation_id": self._correlation_id})
        
        # Ensure all tasks are cleared
        self._disk_monitor_task = None
        self._warmup_task = None
        self._telemetry_task = None
        self._tasks.clear()
        
        # Close all cache layers
        for layer_type, layer in self._cache_layers.items():
            try:
                self._logger.debug(f"Closing {layer_type} layer", extra={"correlation_id": self._correlation_id})
                await layer.close()
            except Exception as e:
                self._logger.error(f"Error closing {layer_type} layer: {e}", extra={"correlation_id": self._correlation_id})
        
        # Close Redis client if it exists
        if hasattr(self, '_redis') and self._redis:
            try:
                self._logger.debug("Closing Redis client", extra={"correlation_id": self._correlation_id})
                await self._redis.aclose()  # Use aclose() instead of close()
                self._redis = None
            except Exception as e:
                self._logger.error(f"Error closing Redis client: {e}", extra={"correlation_id": self._correlation_id})
        
        self._logger.debug("CacheManager successfully closed", extra={"correlation_id": self._correlation_id})

    async def _start_services(self) -> None:
        """Start background services like telemetry, invalidation listeners, etc."""
        try:
            # Start telemetry collection
            if hasattr(self, '_telemetry') and self._telemetry and self._telemetry.enabled:
                await self._telemetry.start()
            
            # Start invalidation manager
            if hasattr(self, '_invalidation_manager') and self._invalidation_manager and self._invalidation_manager.enabled:
                await self._invalidation_manager.start()
                
                # Add invalidation callbacks
                async def handle_key_invalidation(data: Dict[str, Any]) -> None:
                    """Handle invalidation for a specific key."""
                    key = data.get('key')
                    if key:
                        # Delete from all cache layers
                        for layer in self._cache_layers.values():
                            await layer.delete(self._namespace_key(key))
                
                async def handle_pattern_invalidation(data: Dict[str, Any]) -> None:
                    """Handle invalidation for a pattern (multiple keys)."""
                    pattern = data.get('pattern')
                    if pattern:
                        # We'd need a way to list keys matching a pattern
                        # For now, this is a placeholder
                        pass
                
                async def handle_namespace_invalidation(data: Dict[str, Any]) -> None:
                    """Handle invalidation for an entire namespace."""
                    namespace = data.get('namespace')
                    if namespace == self._config.namespace:
                        # Clear all cache layers for this namespace
                        await self.clear()
                
                self._invalidation_manager.add_callback(InvalidationEvent.KEY, handle_key_invalidation)
                self._invalidation_manager.add_callback(InvalidationEvent.PATTERN, handle_pattern_invalidation)
                self._invalidation_manager.add_callback(InvalidationEvent.NAMESPACE, handle_namespace_invalidation)
            
            # Perform cache warmup if enabled
            if self._config.enable_warmup and self._config.warmup_on_start:
                await self._cache_warmup.warmup(self)
        except Exception as e:
            self._logger.error(f"Error starting services: {e}", extra={"correlation_id": self._correlation_id})

    async def _propagate_to_higher_layers(self, key: str, value: Any, source_layer: CacheLayerType):
        """Propagate a value found in a lower-priority cache layer to all higher-priority layers.
        
        Args:
            key: The cache key
            value: The value to propagate
            source_layer: The layer type where the value was found
        """
        if not self._config.use_layered_cache or not self._config.read_through:
            return
            
        try:
            # Find the index of the source layer in the layer order
            layer_types = [layer.type for layer in self._config.cache_layers if layer.enabled]
            if source_layer not in layer_types:
                return
                
            source_index = layer_types.index(source_layer)
            
            # Propagate to all higher-priority layers (lower indices)
            for i in range(source_index):
                target_layer_type = layer_types[i]
                if target_layer_type in self._cache_layers:
                    target_layer = self._cache_layers[target_layer_type]
                    # Use the TTL configured for this layer
                    ttl = next((layer.ttl for layer in self._config.cache_layers 
                               if layer.type == target_layer_type), None)
                    await target_layer.set(key, value, ttl)
                    self._logger.debug(
                        f"Propagated key {key} from {source_layer} to {target_layer_type}",
                        extra={"correlation_id": self._correlation_id}
                    )
        except Exception as e:
            self._logger.error(
                f"Error propagating key {key} to higher layers: {e}",
                extra={"correlation_id": self._correlation_id}
            )

    def _get_disk_layer_usage(self) -> float:
        """Get current disk cache usage as percentage.
        
        Returns:
            float: Disk usage as percentage (0-100)
        """
        try:
            disk_usage = shutil.disk_usage(self._config.cache_dir)
            percent_used = (disk_usage.used / disk_usage.total) * 100
            return round(percent_used, 2)
        except Exception as e:
            self._logger.error(
                f"Error getting disk usage: {e}",
                extra={"correlation_id": self._correlation_id}
            )
            return 0.0

    async def _set_in_layer(self, layer, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """Set a value in a specific cache layer.
        
        Args:
            layer: The cache layer object
            key: Cache key
            value: Value to store
            ttl: Time to live in seconds
            
        Returns:
            bool: True if set successfully, False otherwise
            
        Raises:
            CacheError: If there's an error setting the value in the layer
        """
        try:
            if hasattr(layer, 'set'):
                return await layer.set(key, value, ttl)
            else:
                error_msg = "Cache layer does not have 'set' method"
                logger.error(error_msg)
                raise CacheError(error_msg)
        except Exception as e:
            error_msg = f"Error setting key {key} in layer: {str(e)}"
            logger.error(error_msg)
            if isinstance(e, CacheError):
                raise
            else:
                raise CacheError(error_msg) from e

    async def _publish_invalidation(self, key: str) -> bool:
        """Publish cache invalidation message to other nodes.
        
        Args:
            key: Cache key to invalidate
            
        Returns:
            bool: True if invalidation was published successfully
        """
        if not self._redis_client:
            logger.debug("Redis client not available for cross-node invalidation")
            return False
            
        try:
            # Create invalidation message
            invalidation_msg = {
                "key": key,
                "timestamp": time.time(),
                "source_id": self._instance_id  # Don't invalidate on source node
            }
            
            # Serialize the message
            message = json.dumps(invalidation_msg)
            
            # Publish to the invalidation channel
            channel = f"{self._config.namespace}:invalidation"
            await self._redis_client.publish(channel, message)
            logger.debug(f"Published invalidation for key: {key}")
            return True
        except Exception as e:
            logger.error(f"Error publishing invalidation for key {key}: {str(e)}")
            return False

    async def _cleanup_disk_cache(self, aggressive: bool = False) -> int:
        """Alias for _clean_disk_cache to maintain backward compatibility.
        
        Args:
            aggressive: If True, perform more aggressive cleanup
            
        Returns:
            int: Number of items removed from cache
        """
        return await self._clean_disk_cache(aggressive=aggressive)

    def _compress_data(self, value: Any) -> Any:
        """Compress data if it's large enough.
        
        Args:
            value: The data to potentially compress
            
        Returns:
            Any: Compressed data or original data if compression isn't applicable
        """
        return compress_data(value, self._config)

    def _decompress_data(self, value: Any) -> Any:
        """Decompress data that was previously compressed.
        
        Args:
            value: The potentially compressed data
            
        Returns:
            Any: Decompressed data or original data if not compressed
        """
        return decompress_data(value, self._config)

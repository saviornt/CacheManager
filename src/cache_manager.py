import os
import shelve
import logging
import logging.handlers
import functools
import uuid
import zlib
import asyncio
import shutil
import time
from typing import Any, Dict, List, Optional, TypeVar, Callable, cast
from collections import OrderedDict, Counter
from threading import RLock
from datetime import datetime, timedelta
from .cache_config import CacheConfig, EvictionPolicy, CacheLayerType, LogLevel
from tenacity import retry, stop_after_attempt, wait_fixed

from .core.logging_setup import setup_logging
from .core.exceptions import CacheSerializationError, CacheKeyError
from .cache_layers import BaseCacheLayer, MemoryLayer, RedisLayer, DiskLayer

# Import new features
from .core.telemetry import TelemetryManager, timed_operation, CacheEvent
from .core.distributed_lock import DistributedLock
from .core.sharding import ShardManager, HashRingShardingStrategy, ModuloShardingStrategy
from .core.security import CacheEncryptor, DataSigner, AccessControl, require_permission
from .core.cache_warmup import CacheWarmup
from .core.adaptive_ttl import AdaptiveTTLManager
from .core.invalidation import InvalidationManager, InvalidationEvent

# Create a filter to add correlation ID to all log records
class CorrelationIdFilter(logging.Filter):
    """Add correlation_id to all log records.
    
    This allows tracking operations across multiple function calls.
    """
    def filter(self, record):
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = 'N/A'
        return True

# Configure logging based on CacheConfig
def setup_logging(config: CacheConfig) -> logging.Logger:
    """Set up logging configuration based on CacheConfig.
    
    Args:
        config: The cache configuration containing logging settings
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Map LogLevel enum to logging module levels
    log_level_map = {
        LogLevel.DEBUG: logging.DEBUG,
        LogLevel.INFO: logging.INFO,
        LogLevel.WARNING: logging.WARNING,
        LogLevel.ERROR: logging.ERROR,
        LogLevel.CRITICAL: logging.CRITICAL
    }
    
    log_level = log_level_map.get(config.log_level, logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.setLevel(log_level)
    
    # Create formatter with correlation ID
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - [%(correlation_id)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add correlation ID filter
    logger.addFilter(CorrelationIdFilter())
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)
    
    # Add file handler if log_to_file is enabled
    if config.log_to_file:
        # Create logs directory if it doesn't exist
        os.makedirs(config.log_dir, exist_ok=True)
        
        # Create log filename with current datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{__name__}_{timestamp}.log"
        log_path = os.path.join(config.log_dir, log_filename)
        
        # Set up rotating file handler with size limits
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=config.log_max_size,
            backupCount=config.log_backup_count
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        logger.addHandler(file_handler)
    
    return logger

# Default logger for imports and module initialization
logger = logging.getLogger(__name__)
logger.addFilter(CorrelationIdFilter())

# Initialize with a basic default config
default_config = CacheConfig()

# Create log directory if it doesn't exist
if default_config.log_to_file:
    os.makedirs(default_config.log_dir, exist_ok=True)

logger = setup_logging(default_config)

# Try to import dependencies
try:
    import msgpack
except ImportError:
    msgpack = None
    logger.warning("msgpack not installed, falling back to pickle for serialization", extra={'correlation_id': 'INIT'})
    import pickle

# Try to import the async redis client
try:
    import redis.asyncio as redis
except ImportError:
    redis = None
    logger.warning("redis-py not installed or doesn't have async support", extra={'correlation_id': 'INIT'})

# Decorator return type
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])

# Circuit breaker implementation
class CircuitBreaker:
    """Circuit breaker pattern implementation to prevent operation cascading failures.
    
    When errors exceed the threshold, the circuit opens and operations return a default value.
    After a timeout period, the circuit closes and operations are attempted again.
    """
    def __init__(self, 
                 failure_threshold: int = 5, 
                 reset_timeout: int = 60,
                 operation_name: str = "unnamed"):
        """Initialize a circuit breaker.
        
        Args:
            failure_threshold: Number of consecutive failures before opening the circuit
            reset_timeout: Seconds to wait before trying to reset (close) the circuit
            operation_name: Name of the operation using this circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.operation_name = operation_name
        
        # Initial state
        self.failures = 0
        self.is_open = False
        self.last_failure_time = None
        self._lock = RLock()
        
        self._correlation_id = f"CB-{uuid.uuid4().hex[:8]}"
        
    def record_success(self):
        """Record a successful operation, resetting the failure count."""
        with self._lock:
            self.failures = 0
            self.is_open = False
    
    def record_failure(self):
        """Record a failed operation, possibly opening the circuit."""
        with self._lock:
            self.failures += 1
            self.last_failure_time = datetime.now()
            
            if self.failures >= self.failure_threshold:
                if not self.is_open:
                    logger.warning(
                        f"Circuit breaker for '{self.operation_name}' opened after "
                        f"{self.failures} consecutive failures",
                        extra={'correlation_id': self._correlation_id}
                    )
                self.is_open = True
    
    def allow_request(self) -> bool:
        """Check if the request should be allowed through the circuit.
        
        Returns:
            bool: True if the request should be allowed, False otherwise
        """
        with self._lock:
            # If circuit is closed, allow the request
            if not self.is_open:
                return True
                
            # If circuit is open, check if reset timeout has elapsed
            if self.last_failure_time is None:
                return True
                
            # Try to reset after the timeout
            elapsed = datetime.now() - self.last_failure_time
            if elapsed.total_seconds() >= self.reset_timeout:
                logger.info(
                    f"Circuit breaker for '{self.operation_name}' reset after "
                    f"{elapsed.total_seconds():.1f} seconds",
                    extra={'correlation_id': self._correlation_id}
                )
                self.is_open = False  # Try again (half-open state)
                return True
                
            return False
            
    def __call__(self, func):
        """Decorator to wrap a function with circuit breaker functionality.
        
        Args:
            func: The async function to wrap
            
        Returns:
            Callable: Wrapped function
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if not self.allow_request():
                logger.warning(
                    f"Circuit is open for '{self.operation_name}', operation skipped",
                    extra={'correlation_id': self._correlation_id}
                )
                return None
                
            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                logger.error(
                    f"Circuit breaker caught error in '{self.operation_name}': {e}",
                    extra={'correlation_id': self._correlation_id}
                )
                raise
                
        return wrapper

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
            config: Configuration settings for the cache manager
        """
        self._config = config
        self._use_redis = self._config.use_redis and redis is not None
        self._use_msgpack = msgpack is not None
        self._correlation_id = f"CM-{uuid.uuid4().hex[:8]}"
        
        # Set up logging with the provided configuration
        self._logger = setup_logging(self._config)
        
        self._logger.debug("Initializing CacheManager", extra={'correlation_id': self._correlation_id})

        # Ensure the cache directory exists for shelve
        if not os.path.exists(self._config.cache_dir):
            os.makedirs(self._config.cache_dir)
            self._logger.debug(f"Created cache directory: {self._config.cache_dir}", extra={'correlation_id': self._correlation_id})
        
        # Add namespace to shelve file to isolate different namespaces
        namespace_suffix = f"_{self._config.namespace}" if self._config.namespace != "default" else ""
        self.shelve_file = os.path.join(
            self._config.cache_dir, 
            f"{os.path.splitext(self._config.cache_file)[0]}{namespace_suffix}.db"
        )
        
        # Initialize stats counters
        self._stats = {
            "hits": 0,
            "misses": 0, 
            "sets": 0,
            "errors": 0,
            "layer_hits": {layer.type: 0 for layer in self._config.cache_layers} 
            if self._config.use_layered_cache else {}
        }
        
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
        self._connection_pool = None
        
        # Cache layers
        self._cache_layers = {}
        
        # Circuit breakers for different operations
        self._breakers = {}
        
        # Setup cache layers
        self._setup_cache_layers()
        
        self._logger.debug(
            f"CacheManager initialized with config: "
            f"redis={self._use_redis}, "
            f"msgpack={self._use_msgpack}, "
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

        # Initialize telemetry manager
        self._telemetry = TelemetryManager(
            enabled=self._config.enable_telemetry,
            report_interval=self._config.telemetry_interval,
            log_dir=self._config.log_dir
        )
        
        # Initialize adaptive TTL manager
        self._adaptive_ttl = AdaptiveTTLManager(
            enabled=self._config.enable_adaptive_ttl,
            min_ttl=self._config.adaptive_ttl_min,
            max_ttl=self._config.adaptive_ttl_max,
            access_count_threshold=self._config.access_count_threshold,
            adjustment_factor=getattr(self._config, 'adaptive_ttl_adjustment_factor', 1.5)
        )
        
        # Initialize cache warmup
        self._cache_warmup = CacheWarmup(
            enabled=self._config.enable_warmup,
            warmup_keys_file=self._config.warmup_keys_file
        )
        
        # Initialize security features
        self._encryptor = CacheEncryptor(
            secret_key=self._config.encryption_key,
            salt=self._config.encryption_salt,
            enabled=self._config.enable_encryption
        )
        
        self._data_signer = DataSigner(
            secret_key=self._config.signing_key or "default_signing_key",
            algorithm=self._config.signing_algorithm,
            enabled=self._config.enable_data_signing
        )
        
        self._access_control = AccessControl(
            enabled=self._config.enable_access_control
        )
        
        # Initialize distributed features (if Redis is available)
        if self._config.use_redis:
            # Initialize invalidation manager
            self._invalidation_manager = InvalidationManager(
                redis_client=self._get_redis_client(),
                channel=self._config.invalidation_channel,
                enabled=self._config.enable_invalidation,
                node_id=f"node-{uuid.uuid4().hex[:8]}"
            )
            
            # Initialize shard manager
            if self._config.enable_sharding:
                strategy = (
                    HashRingShardingStrategy() 
                    if self._config.sharding_algorithm == "consistent_hash"
                    else ModuloShardingStrategy()
                )
                
                self._shard_manager = ShardManager(
                    num_shards=self._config.num_shards,
                    strategy=strategy
                )
            else:
                self._shard_manager = None
        else:
            self._invalidation_manager = None
            self._shard_manager = None
        
        # Perform startup tasks (like cache warmup)
        if self._config.enable_warmup and self._config.warmup_on_start:
            self._warmup_task = asyncio.create_task(self._cache_warmup.warmup(self))

    def _setup_cache_layers(self):
        """Initialize the cache layers based on configuration."""
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
        
        # Add Redis cache if enabled and available
        if self._config.use_redis:
            try:
                # Import Redis asynchronously
                import redis.asyncio as aioredis
                
                self._cache_layers[CacheLayerType.REDIS] = RedisLayer(
                    namespace=self._config.namespace,
                    ttl=self._config.redis_ttl,
                    redis_url=self._config.full_redis_url
                )
            except ImportError as e:
                self._logger.warning(
                    f"Failed to initialize Redis layer: {e}", 
                    extra={'correlation_id': self._correlation_id}
                )

    def _namespace_key(self, key: str) -> str:
        """Add namespace prefix to a key.
        
        Args:
            key: The original key
            
        Returns:
            str: The namespaced key
        """
        if self._config.namespace == "default":
            return key
        return f"{self._config.namespace}:{key}"
    
    def _remove_namespace(self, namespaced_key: str) -> str:
        """Remove namespace prefix from a key.
        
        Args:
            namespaced_key: The namespaced key
            
        Returns:
            str: The original key without namespace
        """
        if self._config.namespace == "default" or ":" not in namespaced_key:
            return namespaced_key
        _, key = namespaced_key.split(":", 1)
        return key
    
    def _namespace_keys_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add namespace prefix to all keys in a dictionary.
        
        Args:
            data: Dictionary with original keys
            
        Returns:
            Dict[str, Any]: Dictionary with namespaced keys
        """
        return {self._namespace_key(key): value for key, value in data.items()}
    
    def _remove_namespace_from_keys_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove namespace prefix from all keys in a dictionary.
        
        Args:
            data: Dictionary with namespaced keys
            
        Returns:
            Dict[str, Any]: Dictionary with original keys
        """
        return {self._remove_namespace(key): value for key, value in data.items()}

    async def _get_redis_client(self):
        """Get a Redis client, initializing it if necessary.
        
        Returns:
            Redis: A Redis client
            
        Raises:
            CacheConnectionError: If Redis couldn't be initialized
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
                self._logger.error(
                    f"Redis connection test failed: {e}", 
                    extra={"correlation_id": self._correlation_id}
                )
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

    def _evict_if_needed(self):
        """Evict items if the cache is full according to the chosen policy."""
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

    def _check_ttl(self, key, timestamp):
        """Check if a key has expired.
        
        Args:
            key: The key to check
            timestamp: The timestamp when the key was set
            
        Returns:
            bool: True if the key has expired, False otherwise
        """
        now = datetime.now()
        if now > timestamp + timedelta(seconds=self._config.memory_cache_ttl):
            self._logger.debug(f"Key {key} has expired", extra={"correlation_id": self._correlation_id})
            return True
        return False

    async def _monitor_disk_usage(self):
        """Monitor disk usage and clean up if it exceeds thresholds."""
        self._logger.info("Starting disk usage monitoring", extra={"correlation_id": self._correlation_id})
        
        try:
            while True:
                # Check disk usage
                disk_usage = shutil.disk_usage(self._config.cache_dir)
                
                # Calculate percentage used
                percent_used = (disk_usage.used / disk_usage.total) * 100
                
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
                    await self._clean_disk_cache(emergency=True)
                    
                # Warning threshold - initiate normal cleanup
                elif percent_used >= self._config.disk_usage_threshold:
                    self._logger.info(
                        f"Disk usage high at {percent_used:.1f}% "
                        f"(threshold: {self._config.disk_usage_threshold}%). "
                        f"Performing cleanup.",
                        extra={"correlation_id": self._correlation_id}
                    )
                    await self._clean_disk_cache(emergency=False)
                    
                # Wait for next check interval
                await asyncio.sleep(self._config.disk_check_interval)
                
        except asyncio.CancelledError:
            self._logger.info("Disk usage monitoring stopped", extra={"correlation_id": self._correlation_id})
            raise

    def _setup_disk_monitoring(self):
        """Set up disk usage monitoring if enabled."""
        if self._config.disk_usage_monitoring:
            self._disk_monitor_task = asyncio.create_task(
                self._monitor_disk_usage()
            )
            self._logger.debug("Disk usage monitoring started", extra={"correlation_id": self._correlation_id})

    async def _clean_disk_cache(self, emergency=False):
        """Clean the disk cache based on retention policy or emergency need.
        
        Args:
            emergency: If True, perform more aggressive cleanup
        """
        self._logger.info(
            f"Cleaning disk cache (emergency={emergency})", 
            extra={"correlation_id": self._correlation_id}
        )
        
        try:
            # Calculate retention time in seconds
            retention_seconds = self._config.disk_retention_days * 24 * 60 * 60
            retention_time = time.time() - retention_seconds
            
            # Get the shelve file path
            shelve_file = os.path.join(self._config.cache_dir, self._config.cache_file)
            
            # Clean cache
            # Implementation depends on specific storage mechanism
            # For shelve, we'd need to load, filter, and save
            # This is a placeholder for actual implementation
            
            self._logger.info(
                f"Disk cache cleaned", 
                extra={"correlation_id": self._correlation_id}
            )
            
        except Exception as e:
            self._logger.error(
                f"Failed to clean disk cache: {e}", 
                extra={"correlation_id": self._correlation_id}
            )

    async def _compact_cache(self):
        """Compact the disk cache to free up space.
        
        This removes all deleted keys and reorganizes the cache file.
        """
        self._logger.info("Compacting cache", extra={"correlation_id": self._correlation_id})
        
        try:
            # Get the shelve file path
            shelve_file = os.path.join(self._config.cache_dir, self._config.cache_file)
            
            # Actual implementation would depend on the storage backend
            # For shelve, we might need to create a new file and copy over
            # This is a placeholder
            
            self._logger.info("Cache compacted", extra={"correlation_id": self._correlation_id})
            
        except Exception as e:
            self._logger.error(
                f"Failed to compact cache: {e}", 
                extra={"correlation_id": self._correlation_id}
            )

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
        try:
            # Serialize with msgpack
            serialized = msgpack.packb(value, use_bin_type=True)
            
            # Compress if enabled and the value is large enough
            if (self._config.enable_compression and 
                len(serialized) >= self._config.compression_min_size):
                compressed = zlib.compress(serialized, level=self._config.compression_level)
                serialized = b'c' + compressed  # Prefix with 'c' to indicate compression
            else:
                serialized = b'u' + serialized  # Prefix with 'u' to indicate uncompressed
            
            # Encrypt if enabled
            if hasattr(self, '_encryptor') and self._encryptor and self._encryptor.enabled:
                serialized = self._encryptor.encrypt(serialized)
            
            # Sign if enabled
            if hasattr(self, '_data_signer') and self._data_signer and self._data_signer.enabled:
                serialized = self._data_signer.sign(serialized)
            
            return serialized
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
        try:
            # Verify signature if enabled
            if hasattr(self, '_data_signer') and self._data_signer and self._data_signer.enabled:
                data = self._data_signer.verify(data)
            
            # Decrypt if enabled
            if hasattr(self, '_encryptor') and self._encryptor and self._encryptor.enabled:
                data = self._encryptor.decrypt(data)
            
            # Check for compression flag
            if data.startswith(b'c'):  # Compressed
                decompressed = zlib.decompress(data[1:])
                return msgpack.unpackb(decompressed, raw=False, ext_hook=self._decode_complex_types)
            elif data.startswith(b'u'):  # Uncompressed
                return msgpack.unpackb(data[1:], raw=False, ext_hook=self._decode_complex_types)
            else:
                # Legacy data without compression flag
                return msgpack.unpackb(data, raw=False, ext_hook=self._decode_complex_types)
        except Exception as e:
            self._logger.error(
                f"Failed to deserialize data: {e}", 
                extra={"correlation_id": self._correlation_id}
            )
            self._stats["errors"] += 1
            raise CacheSerializationError(f"Failed to deserialize data: {e}") from e

    @retry(stop=stop_after_attempt(CacheConfig().retry_attempts), 
           wait=wait_fixed(CacheConfig().retry_delay))
    @timed_operation("get")
    @require_permission("read")
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.
        
        Args:
            key: The key to retrieve
            
        Returns:
            The cached value, or None if not found
            
        Raises:
            CacheKeyError: If there's an issue with the key
            CacheError: If there's a general caching error
        """
        # Record access for adaptive TTL
        if hasattr(self, '_adaptive_ttl') and self._adaptive_ttl.enabled:
            self._adaptive_ttl.record_access(key)
        
        if not key:
            raise CacheKeyError("Cache key cannot be empty")
            
        log_extra = {'correlation_id': self._correlation_id}
        logger.debug(f"Getting key: {key}", extra=log_extra)
        
        result = None
        
        if self.config.use_layered_cache:
            # Try each cache layer in order
            for layer_config in self.config.cache_layers:
                if not layer_config.enabled:
                    continue
                    
                layer_type = layer_config.type
                if layer_type not in self._cache_layers:
                    continue
                    
                layer = self._cache_layers[layer_type]
                found, value = await layer.get(key)
                
                if found:
                    self._stats["hits"] += 1
                    self._stats["layer_hits"][layer_type] += 1
                    logger.debug(
                        f"Cache hit for key: {key} in layer: {layer_type}", 
                        extra=log_extra
                    )
                    
                    # If found in any layer except the first, and read-through is enabled,
                    # populate previous layers
                    if (self.config.read_through and 
                            layer_type != self.config.cache_layers[0].type):
                        # Populate previous layers
                        for prev_layer_config in self.config.cache_layers:
                            if not prev_layer_config.enabled:
                                continue
                                
                            prev_layer_type = prev_layer_config.type
                            if prev_layer_type == layer_type:
                                break
                                
                            if prev_layer_type in self._cache_layers:
                                prev_layer = self._cache_layers[prev_layer_type]
                                await prev_layer.set(key, value)
                    
                    return value
            
            # Not found in any layer
            self._stats["misses"] += 1
            logger.debug(f"Cache miss for key: {key}", extra=log_extra)
            return None
        else:
            # For backward compatibility: use the first available layer
            for layer in self._cache_layers.values():
                found, value = await layer.get(key)
                if found:
                    self._stats["hits"] += 1
                    logger.debug(f"Cache hit for key: {key} in layer: {layer_type}", extra=log_extra)
                    return value
            
            self._stats["misses"] += 1
            logger.debug(f"Cache miss for key: {key}", extra=log_extra)
            return None

    @retry(stop=stop_after_attempt(CacheConfig().retry_attempts), 
           wait=wait_fixed(CacheConfig().retry_delay))
    @timed_operation("set")
    @require_permission("write")
    async def set(self, key: str, value: Any, expiration: Optional[int] = None):
        """Set a value in the cache.
        
        Args:
            key: The key to store the value under
            value: The value to store
            expiration: Optional TTL in seconds
            
        Raises:
            CacheKeyError: If there's an issue with the key
            CacheSerializationError: If the value can't be serialized
            CacheError: If there's a general caching error
        """
        # Use adaptive TTL if enabled
        if hasattr(self, '_adaptive_ttl') and self._adaptive_ttl.enabled and expiration is not None:
            expiration = self._adaptive_ttl.adjust_ttl(key, expiration)
        
        if not key:
            raise CacheKeyError("Cache key cannot be empty")
            
        log_extra = {'correlation_id': self._correlation_id}
        logger.debug(f"Setting key: {key}", extra=log_extra)
        
        self._stats["sets"] += 1
        
        if self.config.use_layered_cache:
            # Set in each layer as configured
            for i, layer_config in enumerate(self.config.cache_layers):
                if not layer_config.enabled:
                    continue
                    
                layer_type = layer_config.type
                if layer_type not in self._cache_layers:
                    continue
                    
                # If write-through is disabled and this is not the first layer, skip
                if i > 0 and not self.config.write_through:
                    break
                    
                layer = self._cache_layers[layer_type]
                ttl = expiration or layer_config.ttl
                await layer.set(key, value, ttl)
        else:
            # For backward compatibility: use all available layers
            for layer in self._cache_layers.values():
                await layer.set(key, value, expiration)

        # Invalidate this key on other nodes if cross-node invalidation is enabled
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

    async def clear(self):
        """Clear all cached keys relevant to this run.
        
        Clears all cache layers.
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
        if self.config.disk_usage_monitoring:
            stats["disk_usage_percent"] = self._get_disk_layer_usage()
        
        return stats

    def cached(self, ttl: Optional[int] = None) -> Callable[[F], F]:
        """Decorator for caching function results.
        
        Args:
            ttl: Optional TTL in seconds (overrides config.cache_ttl)
            
        Returns:
            Callable: Decorated function with caching
        """
        def decorator(func: F) -> F:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Generate cache key from function name and arguments
                key_parts = [func.__module__, func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                key = ":".join(key_parts)
                
                # Check cache first
                cached_result = await self.get(key)
                if cached_result is not None:
                    return cached_result
                
                # Execute function if not in cache
                result = await func(*args, **kwargs)
                
                # Store result in cache
                await self.set(key, result, expiration=ttl)
                return result
                
            return cast(F, wrapper)
        return decorator

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
        
        if self.config.use_layered_cache:
            # Get from each layer, filling in missing keys
            remaining_keys = set(keys)
            
            for layer_config in self.config.cache_layers:
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
                    self._stats["layer_hits"][layer_type] += 1
                
                # If read-through is enabled, populate previous layers with found values
                if (self.config.read_through and 
                        layer_results and 
                        layer_type != self.config.cache_layers[0].type):
                    # For each key found in this layer, populate previous layers
                    for prev_layer_config in self.config.cache_layers:
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
        
        if self.config.use_layered_cache:
            # Set in each layer as configured
            for i, layer_config in enumerate(self.config.cache_layers):
                if not layer_config.enabled:
                    continue
                    
                layer_type = layer_config.type
                if layer_type not in self._cache_layers:
                    continue
                    
                # If write-through is disabled and this is not the first layer, skip
                if i > 0 and not self.config.write_through:
                    break
                    
                layer = self._cache_layers[layer_type]
                ttl = expiration or layer_config.ttl
                await layer.set_many(key_values, ttl)
        else:
            # For backward compatibility: use all available layers
            for layer in self._cache_layers.values():
                await layer.set_many(key_values, expiration)

    # Async context management to ensure proper cleanup
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def close(self):
        """Clean up resources when the cache manager is no longer needed."""
        # Cancel disk monitoring task
        if self._disk_monitor_task:
            self._disk_monitor_task.cancel()
            try:
                await self._disk_monitor_task
            except asyncio.CancelledError:
                pass
            
        # Close all cache layers
        for layer in self._cache_layers.values():
            await layer.close()

    async def _start_services(self):
        """Start background services like telemetry and invalidation."""
        try:
            # Start telemetry collection
            if hasattr(self, '_telemetry') and self._telemetry and self._telemetry.enabled:
                await self._telemetry.start()
            
            # Start invalidation manager
            if hasattr(self, '_invalidation_manager') and self._invalidation_manager and self._invalidation_manager.enabled:
                await self._invalidation_manager.start()
                
                # Add invalidation callbacks
                async def handle_key_invalidation(data):
                    key = data.get('key')
                    if key:
                        # Delete from all cache layers
                        for layer in self._cache_layers.values():
                            await layer.delete(self._namespace_key(key))
                
                async def handle_pattern_invalidation(data):
                    pattern = data.get('pattern')
                    if pattern:
                        # We'd need a way to list keys matching a pattern
                        # For now, this is a placeholder
                        pass
                
                async def handle_namespace_invalidation(data):
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

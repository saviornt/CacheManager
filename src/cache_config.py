import os
from enum import Enum
from typing import List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

load_dotenv()

class EvictionPolicy(str, Enum):
    """Enum defining cache eviction policies.
    
    Available policies:
    - LRU: Least Recently Used - evicts least recently accessed items first
    - FIFO: First In First Out - evicts oldest items first
    - LFU: Least Frequently Used - evicts least frequently accessed items
    """
    LRU = "lru"
    FIFO = "fifo"
    LFU = "lfu"

class CacheLayerType(str, Enum):
    """Enum defining cache layer types.
    
    Available types:
    - MEMORY: In-memory cache (fastest, but volatile)
    - REDIS: Redis cache (networked, shared across instances)
    - DISK: Local disk storage via shelve (persistent, but slow)
    """
    MEMORY = "memory"
    REDIS = "redis"
    DISK = "disk"

class LogLevel(str, Enum):
    """Enum defining log levels.
    
    Available levels:
    - DEBUG: Detailed debugging information
    - INFO: Confirmation that things are working as expected
    - WARNING: Indication that something unexpected happened
    - ERROR: Due to a more serious problem, the software hasn't been able to perform a function
    - CRITICAL: A serious error indicating the program may be unable to continue running
    """
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class Environment(str, Enum):
    """Enum defining environment types.
    
    Available environments:
    - DEV: Development environment
    - TEST: Testing environment
    - PROD: Production environment
    """
    DEV = "dev"
    TEST = "test"
    PROD = "prod"

class CacheLayerConfig(BaseModel):
    """Configuration for a single cache layer.
    
    Defines the type, TTL, and other settings for a specific cache layer.
    """
    type: CacheLayerType
    ttl: int
    enabled: bool = True
    weight: int = Field(default=1, description="For future use with weighted distribution")
    max_size: Optional[int] = Field(default=None, description="Size limit for this layer (None = use parent setting)")

class CacheConfig(BaseModel):
    """Configuration for the CacheManager.
    
    Provides settings for cache storage, Redis connection, and retry behavior.
    """
    # Cache settings
    cache_dir: str = Field(
        default_factory=lambda: os.getenv("CACHE_DIR", ".cache"),
        description="Directory where cache files are stored"
    )
    cache_file: str = Field(
        default_factory=lambda: os.getenv("CACHE_FILE", "cache.db"),
        description="Filename for disk cache storage"
    )
    cache_max_size: int = Field(
        default_factory=lambda: int(os.getenv("CACHE_MAX_SIZE", "5000")),
        description="Maximum number of items to store in the cache"
    )
    cache_ttl: float = Field(
        default_factory=lambda: float(os.getenv("CACHE_TTL", "300.0")),
        description="Default time-to-live for cache entries in seconds"
    )
    eviction_policy: EvictionPolicy = Field(
        default_factory=lambda: EvictionPolicy(os.getenv("EVICTION_POLICY", "lru").lower()),
        description="Policy for evicting items when cache is full"
    )
    namespace: str = Field(
        default_factory=lambda: os.getenv("CACHE_NAMESPACE", "default"),
        description="Namespace for cache keys to avoid collisions"
    )
    
    # Redis settings
    use_redis: bool = Field(
        default_factory=lambda: os.getenv("USE_REDIS", "false").lower() in ("true", "1", "yes"),
        description="Whether to use Redis as a cache backend"
    )
    redis_url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost"),
        description="Base URL for Redis connection"
    )
    redis_port: int = Field(
        default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")),
        description="Port for Redis connection"
    )
    redis_username: str = Field(
        default_factory=lambda: os.getenv("REDIS_USERNAME", ""),
        description="Username for Redis authentication"
    )
    redis_password: str = Field(
        default_factory=lambda: os.getenv("REDIS_PASSWORD", ""),
        description="Password for Redis authentication"
    )
    
    # Memory cache settings
    memory_cache_ttl: int = Field(
        default_factory=lambda: int(os.getenv("MEMORY_CACHE_TTL", "60")),
        description="TTL for in-memory cache entries in seconds"
    )
    memory_cache_enabled: bool = Field(
        default_factory=lambda: os.getenv("MEMORY_CACHE_ENABLED", "true").lower() in ("true", "1", "yes"),
        description="Whether to use in-memory caching"
    )
    
    # Hybrid caching settings
    use_layered_cache: bool = Field(
        default_factory=lambda: os.getenv("USE_LAYERED_CACHE", "false").lower() in ("true", "1", "yes"),
        description="Whether to use multiple cache layers with different speeds/persistence"
    )
    cache_layers: List[CacheLayerConfig] = Field(
        default_factory=list,
        description="Configuration for each cache layer when using layered caching"
    )
    write_through: bool = Field(
        default_factory=lambda: os.getenv("CACHE_WRITE_THROUGH", "true").lower() in ("true", "1", "yes"),
        description="Whether to write to all cache layers on set operations"
    )
    read_through: bool = Field(
        default_factory=lambda: os.getenv("CACHE_READ_THROUGH", "true").lower() in ("true", "1", "yes"),
        description="Whether to read from slower layers when item not found in faster layers"
    )
    
    # Cache compression
    enable_compression: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_COMPRESSION", "false").lower() in ("true", "1", "yes"),
        description="Whether to compress cache entries to save space"
    )
    compression_min_size: int = Field(
        default_factory=lambda: int(os.getenv("COMPRESSION_MIN_SIZE", "1024")),
        description="Minimum size in bytes for compression to be applied"
    )
    compression_level: int = Field(
        default_factory=lambda: int(os.getenv("COMPRESSION_LEVEL", "6")),
        description="Compression level (1-9) for zlib compression"
    )
    
    # Disk usage monitoring and cleanup settings
    disk_usage_monitoring: bool = Field(
        default_factory=lambda: os.getenv("DISK_USAGE_MONITORING", "true").lower() in ("true", "1", "yes"),
        description="Whether to monitor disk usage and perform cleanup"
    )
    disk_usage_threshold: float = Field(
        default_factory=lambda: float(os.getenv("DISK_USAGE_THRESHOLD", "75.0")),
        description="Percentage threshold (0-100) to trigger cleanup"
    )
    disk_critical_threshold: float = Field(
        default_factory=lambda: float(os.getenv("DISK_CRITICAL_THRESHOLD", "90.0")),
        description="Critical percentage threshold for aggressive cleanup"
    )
    disk_check_interval: int = Field(
        default_factory=lambda: int(os.getenv("DISK_CHECK_INTERVAL", "3600")),
        description="How often to check disk usage (in seconds)"
    )
    disk_retention_days: int = Field(
        default_factory=lambda: int(os.getenv("DISK_RETENTION_DAYS", "30")),
        description="Default days to keep cached items during cleanup"
    )

    # Retry settings
    retry_attempts: int = Field(
        default_factory=lambda: int(os.getenv("RETRY_ATTEMPTS", "3")),
        description="Number of retry attempts for failed operations"
    )
    retry_delay: int = Field(
        default_factory=lambda: int(os.getenv("RETRY_DELAY", "2")),
        description="Delay between retry attempts in seconds"
    )
    
    # Environment and logging settings
    environment: Environment = Field(
        default_factory=lambda: Environment(os.getenv("ENV", "dev").lower()),
        description="Current environment (dev, test, prod)"
    )
    log_level: LogLevel = Field(
        default_factory=lambda: {
            "dev": LogLevel.DEBUG,
            "test": LogLevel.INFO,
            "prod": LogLevel.WARNING
        }[os.getenv("ENV", "dev").lower()],
        description="Logging level based on environment"
    )
    log_dir: str = Field(
        default_factory=lambda: os.getenv("LOG_DIR", "./logs"),
        description="Directory where log files are stored"
    )
    log_to_file: bool = Field(
        default_factory=lambda: os.getenv("LOG_TO_FILE", "false").lower() in ("true", "1", "yes")
        or os.getenv("ENV", "dev").lower() == "prod",
        description="Whether to write logs to file in addition to console"
    )
    log_max_size: int = Field(
        default_factory=lambda: int(os.getenv("LOG_MAX_SIZE", "10485760")),
        description="Maximum size of log files in bytes (10MB default)"
    )
    log_backup_count: int = Field(
        default_factory=lambda: int(os.getenv("LOG_BACKUP_COUNT", "5")),
        description="Number of log file backups to keep"
    )
    
    # Telemetry and performance monitoring
    enable_telemetry: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_TELEMETRY", "false").lower() in ("true", "1", "yes"),
        description="Whether to collect telemetry data for performance monitoring"
    )
    telemetry_interval: int = Field(
        default_factory=lambda: int(os.getenv("TELEMETRY_INTERVAL", "60")),
        description="Interval in seconds for collecting telemetry data"
    )
    metrics_collection: bool = Field(
        default_factory=lambda: os.getenv("METRICS_COLLECTION", "true").lower() in ("true", "1", "yes"),
        description="Whether to collect cache performance metrics"
    )
    
    # Cache warmup settings
    enable_warmup: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_WARMUP", "false").lower() in ("true", "1", "yes"),
        description="Whether to pre-warm the cache with frequently used keys"
    )
    warmup_keys_file: Optional[str] = Field(
        default_factory=lambda: os.getenv("WARMUP_KEYS_FILE", None),
        description="Path to file containing keys for cache warmup"
    )
    warmup_on_start: bool = Field(
        default_factory=lambda: os.getenv("WARMUP_ON_START", "false").lower() in ("true", "1", "yes"),
        description="Whether to perform cache warmup on startup"
    )
    
    # Adaptive TTL settings
    enable_adaptive_ttl: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_ADAPTIVE_TTL", "false").lower() in ("true", "1", "yes"),
        description="Whether to adjust TTL based on access patterns"
    )
    adaptive_ttl_min: int = Field(
        default_factory=lambda: int(os.getenv("ADAPTIVE_TTL_MIN", "60")),
        description="Minimum TTL in seconds for adaptive TTL"
    )
    adaptive_ttl_max: int = Field(
        default_factory=lambda: int(os.getenv("ADAPTIVE_TTL_MAX", "86400")),
        description="Maximum TTL in seconds (1 day) for adaptive TTL"
    )
    access_count_threshold: int = Field(
        default_factory=lambda: int(os.getenv("ACCESS_COUNT_THRESHOLD", "10")),
        description="Number of accesses to trigger TTL adjustment"
    )
    adaptive_ttl_adjustment_factor: float = Field(
        default_factory=lambda: float(os.getenv("ADAPTIVE_TTL_ADJUSTMENT_FACTOR", "1.5")),
        description="Factor by which to adjust TTL when threshold is reached"
    )
    
    # Distributed locking settings
    use_distributed_locking: bool = Field(
        default_factory=lambda: os.getenv("USE_DISTRIBUTED_LOCKING", "false").lower() in ("true", "1", "yes"),
        description="Whether to use distributed locking for concurrent operations"
    )
    lock_timeout: int = Field(
        default_factory=lambda: int(os.getenv("LOCK_TIMEOUT", "30")),
        description="Lock expiration time in seconds"
    )
    lock_retry_attempts: int = Field(
        default_factory=lambda: int(os.getenv("LOCK_RETRY_ATTEMPTS", "5")),
        description="Maximum number of retry attempts for acquiring a lock"
    )
    lock_retry_interval: float = Field(
        default_factory=lambda: float(os.getenv("LOCK_RETRY_INTERVAL", "0.2")),
        description="Time between lock retry attempts in seconds"
    )
    
    # Cache sharding settings
    enable_sharding: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_SHARDING", "false").lower() in ("true", "1", "yes"),
        description="Whether to shard the cache across multiple partitions"
    )
    num_shards: int = Field(
        default_factory=lambda: int(os.getenv("NUM_SHARDS", "1")),
        description="Number of cache shards to use"
    )
    sharding_algorithm: str = Field(
        default_factory=lambda: os.getenv("SHARDING_ALGORITHM", "consistent_hash"),
        description="Algorithm for sharding ('consistent_hash' or 'modulo')"
    )
    
    # Cross-node cache invalidation
    enable_invalidation: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_INVALIDATION", "false").lower() in ("true", "1", "yes"),
        description="Whether to enable cross-node cache invalidation"
    )
    invalidation_channel: str = Field(
        default_factory=lambda: os.getenv("INVALIDATION_CHANNEL", "cache:invalidation"),
        description="Redis channel for invalidation messages"
    )
    
    # Security settings
    enable_encryption: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_ENCRYPTION", "false").lower() in ("true", "1", "yes"),
        description="Whether to encrypt cache data"
    )
    encryption_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("ENCRYPTION_KEY", None),
        description="Secret key for encryption"
    )
    encryption_salt: Optional[str] = Field(
        default_factory=lambda: os.getenv("ENCRYPTION_SALT", None),
        description="Salt for encryption key derivation"
    )
    
    enable_data_signing: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_DATA_SIGNING", "false").lower() in ("true", "1", "yes"),
        description="Whether to cryptographically sign cache data"
    )
    signing_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("SIGNING_KEY", None),
        description="Secret key for signing"
    )
    signing_algorithm: str = Field(
        default_factory=lambda: os.getenv("SIGNING_ALGORITHM", "sha256"),
        description="Hash algorithm for signing"
    )
    
    enable_access_control: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_ACCESS_CONTROL", "false").lower() in ("true", "1", "yes"),
        description="Whether to enable access control for cache operations"
    )
    
    # Redis connection security settings
    redis_ssl: bool = Field(
        default_factory=lambda: os.getenv("REDIS_SSL", "false").lower() in ("true", "1", "yes"),
        description="Whether to use SSL for Redis connections"
    )
    redis_ssl_cert_reqs: Optional[str] = Field(
        default_factory=lambda: os.getenv("REDIS_SSL_CERT_REQS", None),
        description="SSL certificate requirements ('none', 'optional', or 'required')"
    )
    redis_ssl_ca_certs: Optional[str] = Field(
        default_factory=lambda: os.getenv("REDIS_SSL_CA_CERTS", None),
        description="Path to CA certificates file for SSL verification"
    )
    
    # Secure connection pool settings
    redis_connection_timeout: float = Field(
        default_factory=lambda: float(os.getenv("REDIS_CONNECTION_TIMEOUT", "5.0")),
        description="Timeout for Redis connections in seconds"
    )
    redis_max_connections: int = Field(
        default_factory=lambda: int(os.getenv("REDIS_MAX_CONNECTIONS", "10")),
        description="Maximum number of Redis connections in the pool"
    )
    
    # Redis Sentinel/Cluster support
    use_redis_sentinel: bool = Field(
        default_factory=lambda: os.getenv("USE_REDIS_SENTINEL", "false").lower() in ("true", "1", "yes"),
        description="Whether to use Redis Sentinel for high availability"
    )
    sentinel_master_name: str = Field(
        default_factory=lambda: os.getenv("SENTINEL_MASTER_NAME", "mymaster"),
        description="Name of the master in Redis Sentinel configuration"
    )
    sentinel_addresses: List[str] = Field(
        default_factory=lambda: os.getenv("SENTINEL_ADDRESSES", "").split(",") if os.getenv("SENTINEL_ADDRESSES") else [],
        description="List of Redis Sentinel addresses"
    )

    # Disk cache settings
    disk_cache_enabled: bool = Field(
        default_factory=lambda: os.getenv("DISK_CACHE_ENABLED", "true").lower() in ("true", "1", "yes"),
        description="Whether to enable disk-based caching"
    )
    disk_cache_ttl: float = Field(
        default_factory=lambda: float(os.getenv("DISK_CACHE_TTL", "3600.0")),
        description="Time-to-live for disk cache entries in seconds (1 hour default)"
    )

    @field_validator("cache_max_size", "retry_attempts", "retry_delay", "redis_port", "memory_cache_ttl", "compression_min_size")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        """Validate that integer fields are positive."""
        if v <= 0:
            raise ValueError(f"Value must be positive, got {v}")
        return v

    @field_validator("disk_usage_threshold", "disk_critical_threshold")
    @classmethod
    def validate_percentage(cls, v: float) -> float:
        """Validate that threshold values are valid percentages."""
        if not 0.0 <= v <= 100.0:
            raise ValueError(f"Percentage value must be between 0 and 100, got {v}")
        return v
    
    @field_validator("compression_level")
    @classmethod
    def validate_compression_level(cls, v: int) -> int:
        """Validate compression level is between 1 and 9."""
        if not 1 <= v <= 9:
            raise ValueError(f"Compression level must be between 1 and 9, got {v}")
        return v
    
    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, v: str) -> str:
        """Validate the namespace string."""
        if not v:
            raise ValueError("Namespace cannot be empty")
        if ":" in v:
            raise ValueError("Namespace cannot contain ':' character")
        return v
    
    @field_validator("cache_layers")
    @classmethod
    def initialize_default_layers(cls, v: List[CacheLayerConfig]) -> List[CacheLayerConfig]:
        """Initialize default cache layers if none provided."""
        if not v:
            return [
                CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60, max_size=1000),
                CacheLayerConfig(type=CacheLayerType.REDIS, ttl=300, enabled=False),
                CacheLayerConfig(type=CacheLayerType.DISK, ttl=3600)
            ]
        return v
    
    @field_validator("adaptive_ttl_min", "adaptive_ttl_max")
    @classmethod
    def validate_adaptive_ttl_range(cls, v: int, info) -> int:
        """Validate that adaptive TTL values are reasonable."""
        if info.field_name == "adaptive_ttl_min" and v < 1:
            raise ValueError(f"Minimum adaptive TTL must be at least 1 second, got {v}")
        if info.field_name == "adaptive_ttl_max" and v < info.data.get("adaptive_ttl_min", 60):
            raise ValueError(f"Maximum adaptive TTL must be greater than minimum ({info.data.get('adaptive_ttl_min', 60)}), got {v}")
        return v
    
    @field_validator("lock_timeout", "lock_retry_attempts", "num_shards", "redis_max_connections")
    @classmethod
    def validate_positive_ints(cls, v: int) -> int:
        """Validate that int fields are positive."""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v
    
    @field_validator("lock_retry_interval", "redis_connection_timeout")
    @classmethod
    def validate_positive_float(cls, v: float) -> float:
        """Validate that float fields are positive."""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v
    
    @field_validator("signing_algorithm")
    @classmethod
    def validate_signing_algorithm(cls, v: str) -> str:
        """Validate the signing algorithm."""
        import hashlib
        if v not in hashlib.algorithms_guaranteed:
            raise ValueError(f"Unsupported hash algorithm: {v}")
        return v
    
    @field_validator("sharding_algorithm")
    @classmethod
    def validate_sharding_algorithm(cls, v: str) -> str:
        """Validate the sharding algorithm."""
        if v not in ("consistent_hash", "modulo"):
            raise ValueError(f"Unsupported sharding algorithm: {v}")
        return v
    
    @property
    def full_redis_url(self) -> str:
        """
        Constructs the full Redis URL based on the individual settings.
        
        Returns:
            str: The complete Redis URL including credentials if provided
        """
        scheme, _, host = self.redis_url.partition("://")
        host = host.split(":")[0]  # remove port if any exists
        
        credentials = ""
        if self.redis_username and self.redis_password:
            credentials = f"{self.redis_username}:{self.redis_password}@"
        elif self.redis_password:
            credentials = f":{self.redis_password}@"
            
        return f"{scheme}://{credentials}{host}:{self.redis_port}"

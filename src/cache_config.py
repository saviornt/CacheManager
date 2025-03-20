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
    weight: int = 1  # For future use with weighted distribution
    max_size: Optional[int] = None  # Size limit for this layer (None = use parent setting)

class CacheConfig(BaseModel):
    """Configuration for the CacheManager.
    
    Provides settings for cache storage, Redis connection, and retry behavior.
    """
    # Cache settings
    cache_dir: str = Field(default_factory=lambda: os.getenv("CACHE_DIR", ".cache"))
    cache_file: str = Field(default_factory=lambda: os.getenv("CACHE_FILE", "cache.db"))
    cache_max_size: int = Field(default_factory=lambda: int(os.getenv("CACHE_MAX_SIZE", "5000")))
    cache_ttl: float = Field(default_factory=lambda: float(os.getenv("CACHE_TTL", "300.0")))
    eviction_policy: EvictionPolicy = Field(
        default_factory=lambda: EvictionPolicy(os.getenv("EVICTION_POLICY", "lru").lower())
    )
    namespace: str = Field(default_factory=lambda: os.getenv("CACHE_NAMESPACE", "default"))
    
    # Redis settings
    use_redis: bool = Field(default_factory=lambda: os.getenv("USE_REDIS", "false").lower() in ("true", "1", "yes"))
    redis_url: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost"))
    redis_port: int = Field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_username: str = Field(default_factory=lambda: os.getenv("REDIS_USERNAME", ""))
    redis_password: str = Field(default_factory=lambda: os.getenv("REDIS_PASSWORD", ""))
    
    # Memory cache settings
    memory_cache_ttl: int = Field(default_factory=lambda: int(os.getenv("MEMORY_CACHE_TTL", "60")))
    memory_cache_enabled: bool = Field(default_factory=lambda: os.getenv("MEMORY_CACHE_ENABLED", "true").lower() in ("true", "1", "yes"))
    
    # Hybrid caching settings
    use_layered_cache: bool = Field(default_factory=lambda: os.getenv("USE_LAYERED_CACHE", "false").lower() in ("true", "1", "yes"))
    cache_layers: List[CacheLayerConfig] = Field(default_factory=list)
    write_through: bool = Field(default_factory=lambda: os.getenv("CACHE_WRITE_THROUGH", "true").lower() in ("true", "1", "yes"))
    read_through: bool = Field(default_factory=lambda: os.getenv("CACHE_READ_THROUGH", "true").lower() in ("true", "1", "yes"))
    
    # Cache compression
    enable_compression: bool = Field(default_factory=lambda: os.getenv("ENABLE_COMPRESSION", "false").lower() in ("true", "1", "yes"))
    compression_min_size: int = Field(default_factory=lambda: int(os.getenv("COMPRESSION_MIN_SIZE", "1024")))  # Min size in bytes for compression
    compression_level: int = Field(default_factory=lambda: int(os.getenv("COMPRESSION_LEVEL", "6")))  # 1-9 for zlib
    
    # Disk usage monitoring and cleanup settings
    disk_usage_monitoring: bool = Field(
        default_factory=lambda: os.getenv("DISK_USAGE_MONITORING", "true").lower() in ("true", "1", "yes")
    )
    disk_usage_threshold: float = Field(
        default_factory=lambda: float(os.getenv("DISK_USAGE_THRESHOLD", "75.0"))
    )  # Percentage threshold (0-100) to trigger cleanup
    disk_critical_threshold: float = Field(
        default_factory=lambda: float(os.getenv("DISK_CRITICAL_THRESHOLD", "90.0"))
    )  # Critical percentage threshold for aggressive cleanup
    disk_check_interval: int = Field(
        default_factory=lambda: int(os.getenv("DISK_CHECK_INTERVAL", "3600"))
    )  # How often to check disk usage (in seconds)
    disk_retention_days: int = Field(
        default_factory=lambda: int(os.getenv("DISK_RETENTION_DAYS", "30"))
    )  # Default days to keep cached items during cleanup

    # Retry settings
    retry_attempts: int = Field(default_factory=lambda: int(os.getenv("RETRY_ATTEMPTS", "3")))
    retry_delay: int = Field(default_factory=lambda: int(os.getenv("RETRY_DELAY", "2")))
    
    # Environment and logging settings
    environment: Environment = Field(
        default_factory=lambda: Environment(os.getenv("ENV", "dev").lower())
    )
    log_level: LogLevel = Field(
        default_factory=lambda: {
            "dev": LogLevel.DEBUG,
            "test": LogLevel.INFO,
            "prod": LogLevel.WARNING
        }[os.getenv("ENV", "dev").lower()]
    )
    log_dir: str = Field(default_factory=lambda: os.getenv("LOG_DIR", "./logs"))
    log_to_file: bool = Field(
        default_factory=lambda: os.getenv("LOG_TO_FILE", "false").lower() in ("true", "1", "yes")
        or os.getenv("ENV", "dev").lower() == "prod"
    )
    log_max_size: int = Field(default_factory=lambda: int(os.getenv("LOG_MAX_SIZE", "10485760")))  # 10MB default
    log_backup_count: int = Field(default_factory=lambda: int(os.getenv("LOG_BACKUP_COUNT", "5")))
    
    # Telemetry and performance monitoring
    enable_telemetry: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_TELEMETRY", "false").lower() in ("true", "1", "yes")
    )
    telemetry_interval: int = Field(default_factory=lambda: int(os.getenv("TELEMETRY_INTERVAL", "60")))  # Interval in seconds
    metrics_collection: bool = Field(
        default_factory=lambda: os.getenv("METRICS_COLLECTION", "true").lower() in ("true", "1", "yes")
    )
    
    # Cache warmup settings
    enable_warmup: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_WARMUP", "false").lower() in ("true", "1", "yes")
    )
    warmup_keys_file: Optional[str] = Field(default_factory=lambda: os.getenv("WARMUP_KEYS_FILE", None))
    warmup_on_start: bool = Field(
        default_factory=lambda: os.getenv("WARMUP_ON_START", "false").lower() in ("true", "1", "yes")
    )
    
    # Adaptive TTL settings
    enable_adaptive_ttl: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_ADAPTIVE_TTL", "false").lower() in ("true", "1", "yes")
    )
    adaptive_ttl_min: int = Field(default_factory=lambda: int(os.getenv("ADAPTIVE_TTL_MIN", "60")))  # Minimum TTL in seconds
    adaptive_ttl_max: int = Field(default_factory=lambda: int(os.getenv("ADAPTIVE_TTL_MAX", "86400")))  # Maximum TTL (1 day)
    access_count_threshold: int = Field(default_factory=lambda: int(os.getenv("ACCESS_COUNT_THRESHOLD", "10")))  # Number of accesses to trigger TTL adjustment
    adaptive_ttl_adjustment_factor: float = Field(default_factory=lambda: float(os.getenv("ADAPTIVE_TTL_ADJUSTMENT_FACTOR", "1.5")))  # How much to adjust TTL by
    
    # NEW SETTINGS BELOW
    
    # Distributed locking settings
    use_distributed_locking: bool = Field(
        default_factory=lambda: os.getenv("USE_DISTRIBUTED_LOCKING", "false").lower() in ("true", "1", "yes")
    )
    lock_timeout: int = Field(default_factory=lambda: int(os.getenv("LOCK_TIMEOUT", "30")))  # Lock expiration time in seconds
    lock_retry_attempts: int = Field(default_factory=lambda: int(os.getenv("LOCK_RETRY_ATTEMPTS", "5")))  # Maximum number of retry attempts
    lock_retry_interval: float = Field(default_factory=lambda: float(os.getenv("LOCK_RETRY_INTERVAL", "0.2")))  # Time between retries in seconds
    
    # Cache sharding settings
    enable_sharding: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_SHARDING", "false").lower() in ("true", "1", "yes")
    )
    num_shards: int = Field(default_factory=lambda: int(os.getenv("NUM_SHARDS", "1")))  # Number of cache shards
    sharding_algorithm: str = Field(default_factory=lambda: os.getenv("SHARDING_ALGORITHM", "consistent_hash"))  # "consistent_hash" or "modulo"
    
    # Cross-node cache invalidation
    enable_invalidation: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_INVALIDATION", "false").lower() in ("true", "1", "yes")
    )
    invalidation_channel: str = Field(default_factory=lambda: os.getenv("INVALIDATION_CHANNEL", "cache:invalidation"))  # Redis channel for invalidation messages
    
    # Security settings
    enable_encryption: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_ENCRYPTION", "false").lower() in ("true", "1", "yes")
    )
    encryption_key: Optional[str] = Field(default_factory=lambda: os.getenv("ENCRYPTION_KEY", None))  # Secret key for encryption
    encryption_salt: Optional[str] = Field(default_factory=lambda: os.getenv("ENCRYPTION_SALT", None))  # Salt for key derivation
    
    enable_data_signing: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_DATA_SIGNING", "false").lower() in ("true", "1", "yes")
    )
    signing_key: Optional[str] = Field(default_factory=lambda: os.getenv("SIGNING_KEY", None))  # Secret key for signing
    signing_algorithm: str = Field(default_factory=lambda: os.getenv("SIGNING_ALGORITHM", "sha256"))  # Hash algorithm for signing
    
    enable_access_control: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_ACCESS_CONTROL", "false").lower() in ("true", "1", "yes")
    )
    
    # Redis connection security settings
    redis_ssl: bool = Field(
        default_factory=lambda: os.getenv("REDIS_SSL", "false").lower() in ("true", "1", "yes")
    )
    redis_ssl_cert_reqs: Optional[str] = Field(default_factory=lambda: os.getenv("REDIS_SSL_CERT_REQS", None))
    redis_ssl_ca_certs: Optional[str] = Field(default_factory=lambda: os.getenv("REDIS_SSL_CA_CERTS", None))
    
    # Secure connection pool settings
    redis_connection_timeout: float = Field(default_factory=lambda: float(os.getenv("REDIS_CONNECTION_TIMEOUT", "5.0")))
    redis_max_connections: int = Field(default_factory=lambda: int(os.getenv("REDIS_MAX_CONNECTIONS", "10")))
    
    # Redis Sentinel/Cluster support
    use_redis_sentinel: bool = Field(
        default_factory=lambda: os.getenv("USE_REDIS_SENTINEL", "false").lower() in ("true", "1", "yes")
    )
    sentinel_master_name: str = Field(default_factory=lambda: os.getenv("SENTINEL_MASTER_NAME", "mymaster"))
    sentinel_addresses: List[str] = Field(default_factory=lambda: os.getenv("SENTINEL_ADDRESSES", "").split(",") if os.getenv("SENTINEL_ADDRESSES") else [])

    # Disk cache settings
    disk_cache_enabled: bool = Field(default_factory=lambda: os.getenv("DISK_CACHE_ENABLED", "true").lower() in ("true", "1", "yes"))
    disk_cache_ttl: float = Field(default_factory=lambda: float(os.getenv("DISK_CACHE_TTL", "3600.0")))  # 1 hour

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

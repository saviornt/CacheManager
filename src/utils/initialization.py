"""Utility for initializing CacheManager components."""

import os
import logging
from typing import Dict, Any

from ..cache_config import CacheConfig, CacheLayerType

logger = logging.getLogger(__name__)

class CacheInitializer:
    """Helper class for initializing CacheManager components.
    
    This class encapsulates the initialization logic for different components
    of the CacheManager, like cache layers, telemetry, encryption, etc.
    """
    
    def __init__(self, config: CacheConfig, correlation_id: str):
        """Initialize the CacheInitializer.
        
        Args:
            config: The configuration to use for initialization
            correlation_id: A unique identifier for logging and tracing
        """
        self.config = config
        self.correlation_id = correlation_id
        
    def setup_cache_layers(self) -> Dict[str, Any]:
        """Set up cache layers based on configuration.
        
        Returns:
            Dictionary containing cache layer instances and related components
        """
        # Import cache layers here to avoid circular import
        from ..cache_layers import MemoryLayer, RedisLayer, DiskLayer
        
        cache_layers = {}
        primary_layer = None
        primary_layer_type = None
        layer_order = [CacheLayerType.MEMORY, CacheLayerType.REDIS, CacheLayerType.DISK]
        
        # Always add memory cache if enabled
        if self.config.memory_cache_enabled:
            cache_layers[CacheLayerType.MEMORY] = MemoryLayer(
                namespace=self.config.namespace,
                ttl=self.config.memory_cache_ttl,
                max_size=self.config.cache_max_size,
                eviction_policy=self.config.eviction_policy
            )
            
            # Use memory as primary layer by default
            if not primary_layer:
                primary_layer = cache_layers[CacheLayerType.MEMORY]
                primary_layer_type = CacheLayerType.MEMORY
        
        # Add disk cache if enabled
        if self.config.disk_cache_enabled:
            # Add namespace to shelve file to isolate different namespaces
            namespace_suffix = (
                f"_{self.config.namespace}" 
                if self.config.namespace != "default" 
                else ""
            )
            
            cache_file = os.path.join(
                self.config.cache_dir, 
                f"{os.path.splitext(self.config.cache_file)[0]}{namespace_suffix}.db"
            )
            
            cache_layers[CacheLayerType.DISK] = DiskLayer(
                namespace=self.config.namespace,
                ttl=self.config.disk_cache_ttl,
                cache_dir=self.config.cache_dir,
                cache_file=cache_file
            )
            
            # Use disk as primary layer if memory is disabled
            if not primary_layer:
                primary_layer = cache_layers[CacheLayerType.DISK]
                primary_layer_type = CacheLayerType.DISK
        
        # Add Redis cache if enabled
        if self.config.use_redis:
            # Try to initialize Redis
            try:
                redis_layer = RedisLayer(
                    namespace=self.config.namespace,
                    ttl=self.config.redis_ttl,
                    host=self.config.redis_host,
                    port=self.config.redis_port,
                    db=self.config.redis_db,
                    password=self.config.redis_password
                )
                cache_layers[CacheLayerType.REDIS] = redis_layer
                
                # Use Redis as primary layer if specifically configured
                if getattr(self.config, 'primary_layer', None) == CacheLayerType.REDIS:
                    primary_layer = cache_layers[CacheLayerType.REDIS]
                    primary_layer_type = CacheLayerType.REDIS
            except Exception as e:
                logger.error(f"Failed to initialize Redis layer: {e}")
                
        # If no layers were enabled, add memory layer as fallback
        if not cache_layers:
            logger.warning("No cache layers were enabled; adding memory layer as fallback")
            cache_layers[CacheLayerType.MEMORY] = MemoryLayer(
                namespace=self.config.namespace,
                ttl=self.config.memory_cache_ttl
            )
            primary_layer = cache_layers[CacheLayerType.MEMORY]
            primary_layer_type = CacheLayerType.MEMORY
            
        # Set up layer order for layered caching
        if self.config.use_layered_cache:
            layer_order = [layer.type for layer in self.config.cache_layers 
                           if layer.enabled and layer.type in cache_layers]
            
            # Set primary layer based on config
            if layer_order:
                primary_layer_type = layer_order[0]
                primary_layer = cache_layers[primary_layer_type]
        
        logger.debug(
            f"Cache layers initialized: "
            f"memory={CacheLayerType.MEMORY in cache_layers}, "
            f"redis={CacheLayerType.REDIS in cache_layers}, "
            f"disk={CacheLayerType.DISK in cache_layers}, "
            f"primary={primary_layer_type}",
            extra={"correlation_id": self.correlation_id}
        )
        
        return {
            "cache_layers": cache_layers,
            "primary_layer": primary_layer,
            "primary_layer_type": primary_layer_type,
            "layer_order": layer_order
        }
        
    def setup_core_components(self, redis_client=None) -> Dict[str, Any]:
        """Set up core components like telemetry, security, etc.
        
        Args:
            redis_client: Optional Redis client for components that need it
            
        Returns:
            Dictionary containing core component instances
        """
        # Import core components here to avoid circular import
        from ..core.telemetry import TelemetryManager
        from ..core.adaptive_ttl import AdaptiveTTLManager
        from ..core.cache_warmup import CacheWarmup
        from ..core.security import CacheEncryptor, DataSigner, AccessControl
        from ..core.invalidation import InvalidationManager
        from ..core.sharding import ShardManager, HashRingShardingStrategy, ModuloShardingStrategy
        
        components = {}
        
        # Initialize telemetry manager
        components["telemetry"] = TelemetryManager(
            enabled=self.config.enable_telemetry,
            report_interval=self.config.telemetry_interval,
            log_dir=self.config.log_dir
        )
        
        # Initialize adaptive TTL manager
        components["adaptive_ttl"] = AdaptiveTTLManager(
            enabled=self.config.enable_adaptive_ttl,
            min_ttl=self.config.adaptive_ttl_min,
            max_ttl=self.config.adaptive_ttl_max,
            access_count_threshold=self.config.access_count_threshold,
            adjustment_factor=getattr(self.config, 'adaptive_ttl_adjustment_factor', 1.5)
        )
        
        # Initialize cache warmup
        components["cache_warmup"] = CacheWarmup(
            enabled=self.config.enable_warmup,
            warmup_keys_file=self.config.warmup_keys_file
        )
        
        # Initialize security features
        components["encryptor"] = CacheEncryptor(
            secret_key=self.config.encryption_key,
            salt=self.config.encryption_salt,
            enabled=self.config.enable_encryption
        )
        
        components["data_signer"] = DataSigner(
            secret_key=self.config.signing_key or "default_signing_key",
            algorithm=self.config.signing_algorithm,
            enabled=self.config.enable_data_signing
        )
        
        components["access_control"] = AccessControl(
            enabled=self.config.enable_access_control
        )
        
        # Initialize distributed features if Redis is provided
        if redis_client and self.config.use_redis:
            # Initialize invalidation manager
            components["invalidation_manager"] = InvalidationManager(
                redis_client=redis_client,
                channel=self.config.invalidation_channel,
                enabled=self.config.enable_invalidation,
                node_id=f"node-{self.correlation_id}"
            )
            
            # Initialize shard manager
            if self.config.enable_sharding:
                strategy = (
                    HashRingShardingStrategy() 
                    if self.config.sharding_algorithm == "consistent_hash"
                    else ModuloShardingStrategy()
                )
                
                components["shard_manager"] = ShardManager(
                    num_shards=self.config.num_shards,
                    strategy=strategy
                )
        
        return components 
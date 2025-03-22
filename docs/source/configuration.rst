Configuration
=============

CacheManager offers extensive configuration options to customize caching behavior. This page covers the main configuration options and how to use them.

Basic Configuration
-------------------

The simplest way to configure the cache is by creating a ``CacheConfig`` instance with your desired settings:

.. code-block:: python

    from src.cache_manager import CacheManager
    from src.cache_config import CacheConfig
    
    config = CacheConfig(
        cache_max_size=1000,
        cache_ttl=3600,  # 1 hour in seconds
        eviction_policy="lru"
    )
    
    cache = CacheManager(config=config)

Environment Variables
---------------------

CacheManager supports configuration via environment variables. You can set these in your environment or use a ``.env`` file:

.. code-block:: bash

    # Basic cache settings
    CACHE_MAX_SIZE=5000
    CACHE_TTL=300.0
    EVICTION_POLICY=lru
    CACHE_NAMESPACE=myapp

    # Redis settings
    USE_REDIS=true
    REDIS_URL=redis://localhost
    REDIS_PORT=6379

Multi-layer Caching
-------------------

You can configure multiple cache layers with different characteristics:

.. code-block:: python

    from src.cache_manager import CacheManager
    from src.cache_config import CacheConfig, CacheLayerConfig, CacheLayerType
    
    config = CacheConfig(
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60),
            CacheLayerConfig(type=CacheLayerType.REDIS, ttl=3600),
            CacheLayerConfig(type=CacheLayerType.DISK, ttl=86400)
        ],
        write_through=True,  # Write to all layers on set
        read_through=True    # Check slower layers if not found in faster ones
    )
    
    cache = CacheManager(config=config)

Compression Settings
--------------------

Enable compression for large cache entries:

.. code-block:: python

    config = CacheConfig(
        enable_compression=True,
        compression_min_size=1024,  # Minimum size in bytes for compression
        compression_level=6         # Compression level (1-9)
    )

Security Settings
-----------------

Enable encryption and data signing for sensitive data:

.. code-block:: python

    config = CacheConfig(
        enable_encryption=True,
        encryption_key="your-secret-key",
        enable_data_signing=True,
        signing_key="your-signing-key"
    )

Telemetry and Monitoring
------------------------

Enable performance monitoring:

.. code-block:: python

    config = CacheConfig(
        enable_telemetry=True,
        telemetry_interval=60,  # Collect metrics every 60 seconds
        metrics_collection=True
    )

Advanced Features
-----------------

For advanced features like adaptive TTL, distributed locking, or cache warmup, see the respective documentation sections in the Advanced Features guide.

Complete Configuration Reference
--------------------------------

For a complete list of all configuration options, see the :doc:`api/cache_config` API reference. 
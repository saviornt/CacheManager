Quickstart
==========

Basic Usage
-----------

To get started with CacheManager, you'll first need to import it and create a cache instance:

.. code-block:: python

    from src.cache_manager import CacheManager
    from src.cache_config import CacheConfig

    # Create a basic in-memory cache
    config = CacheConfig(max_size=1000)
    cache = CacheManager(config=config)

    # Store a value in the cache
    cache.set("key1", "value1")

    # Retrieve a value from the cache
    value = cache.get("key1")
    print(value)  # Outputs: value1

Using the Cache Decorator
-------------------------

One of the easiest ways to use CacheManager is with its decorator:

.. code-block:: python

    from src.cache_manager import cached
    from src.cache_config import CacheConfig

    config = CacheConfig(ttl=3600)  # 1 hour TTL

    @cached(config=config)
    def expensive_operation(param1, param2):
        # Perform some expensive operation
        return result

    # First call will compute and cache the result
    result1 = expensive_operation("a", "b")

    # Subsequent calls with same parameters will use the cached value
    result2 = expensive_operation("a", "b")

Multi-layer Caching
-------------------

CacheManager excels at multi-layer caching:

.. code-block:: python

    from src.cache_manager import CacheManager
    from src.cache_config import CacheConfig
    from src.cache_layers import MemoryCacheLayer, DiskCacheLayer

    # Create a hybrid cache with memory and disk layers
    config = CacheConfig(
        layers=[
            MemoryCacheLayer(max_size=1000),
            DiskCacheLayer(directory="/tmp/cache", max_size_bytes=1024*1024*100)
        ]
    )
    
    cache = CacheManager(config=config)

    # The cache will automatically handle storing and retrieving from the appropriate layer
    cache.set("key1", "value1")
    value = cache.get("key1")  # Will check memory first, then disk

See the detailed documentation sections for more advanced features and configurations. 
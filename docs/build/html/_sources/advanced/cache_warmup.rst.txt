Cache Warmup
============

CacheManager provides strategies to pre-populate (warm up) the cache to avoid cold-start performance issues.

Overview
--------

This section covers the cache warmup features of CacheManager.

Basic Usage
-----------

.. code-block:: python

    from src.cache_manager import CacheManager
    from src.cache_config import CacheConfig
    
    config = CacheConfig(
        # cache warmup configuration
    )
    
    cache = CacheManager(config=config)

Configuration Options
---------------------

For detailed configuration options, see the :doc:`../api/cache_config` API reference.

Advanced Usage
--------------

For more advanced cache warmup scenarios, refer to the code examples and API documentation.

Bulk Operations
===============

CacheManager supports efficient bulk operations for getting, setting, and deleting multiple cache items in a single call.

Overview
--------

This section covers the bulk operations features of CacheManager.

Basic Usage
-----------

.. code-block:: python

    from src.cache_manager import CacheManager
    from src.cache_config import CacheConfig
    
    config = CacheConfig(
        # bulk operations configuration
    )
    
    cache = CacheManager(config=config)

Configuration Options
---------------------

For detailed configuration options, see the :doc:`../api/cache_config` API reference.

Advanced Usage
--------------

For more advanced bulk operations scenarios, refer to the code examples and API documentation.

Namespacing
===========

CacheManager provides robust namespace support to organize and isolate cache entries, helping prevent key collisions and enabling efficient cache clearing by category.

Overview
--------

Namespaces act as logical partitions within a cache, similar to directories in a file system. This feature offers:

- Clear organization of cached data by feature, module, or purpose
- Isolated cache regions that can be managed independently
- Easy way to clear subsets of cache data without affecting others
- Prevention of key collisions across different parts of your application

Basic Usage
-----------

To use namespaces with CacheManager:

.. code-block:: python

    from src.cache_manager import CacheManager
    from src.cache_config import CacheConfig
    
    # Create a cache with a global namespace
    config = CacheConfig(namespace="myapp")
    cache = CacheManager(config=config)
    
    # Keys will automatically be prefixed with the namespace
    cache.set("user:1", {"name": "John"})  # Actual key: "myapp:user:1"
    
    # Retrieving uses the same simple syntax
    user = cache.get("user:1")  # Looks up "myapp:user:1" internally

Hierarchical Namespaces
-----------------------

CacheManager supports hierarchical namespaces for finer control:

.. code-block:: python

    # Create a cache with a feature-specific namespace
    user_cache = CacheManager(config=CacheConfig(namespace="myapp:users"))
    product_cache = CacheManager(config=CacheConfig(namespace="myapp:products"))
    
    # Save data in different namespaces
    user_cache.set("1", {"name": "John"})      # Actual key: "myapp:users:1"
    product_cache.set("1", {"name": "Phone"})  # Actual key: "myapp:products:1"
    
    # No collision despite using the same local key "1"
    assert user_cache.get("1") != product_cache.get("1")

Dynamic Namespaces
------------------

You can also change or add namespaces at runtime:

.. code-block:: python

    # Create a cache without a namespace
    cache = CacheManager(config=CacheConfig())
    
    # Set items with various namespaces
    cache.set("key1", "value1", namespace="temp")
    cache.set("key1", "value2", namespace="permanent")
    
    # Retrieve with matching namespace
    assert cache.get("key1", namespace="temp") == "value1"
    assert cache.get("key1", namespace="permanent") == "value2"

Clearing by Namespace
---------------------

One of the most useful features of namespacing is the ability to clear specific sections of the cache:

.. code-block:: python

    # Create a cache with hierarchical namespaces
    cache = CacheManager(config=CacheConfig(namespace="myapp"))
    
    # Set items with different sub-namespaces
    cache.set("key1", "value1", namespace="users")  # Full key: "myapp:users:key1"
    cache.set("key2", "value2", namespace="users")  # Full key: "myapp:users:key2"
    cache.set("key1", "value3", namespace="products")  # Full key: "myapp:products:key1"
    
    # Clear only the users namespace
    cache.clear(namespace="users")
    
    # Users cache is cleared, products remain
    assert cache.get("key1", namespace="users") is None
    assert cache.get("key1", namespace="products") == "value3"

Namespace Patterns and Strategies
---------------------------------

Effective namespace patterns include:

- **Feature-based**: `"app:feature:subfeature"`
- **User-based**: `"app:users:{user_id}"`
- **Environment-based**: `"dev:feature"` vs `"prod:feature"`
- **Version-based**: `"v1:entities"` vs `"v2:entities"`

Implementation Details
----------------------

Internally, CacheManager transforms keys by prefixing them with the namespace and a separator:

```
final_key = f"{namespace}:{key}"
````````````````````````````````

This happens transparently to maintain a clean API while providing namespace isolation. 
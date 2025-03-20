Cache Manager
=============

The core caching system module that provides caching operations with support for multiple backends.

.. automodule:: src.cache_manager
   :members:
   :undoc-members:
   :show-inheritance:
   :no-index:

CacheManager Class
------------------

.. autoclass:: src.cache_manager.CacheManager
   :members:
   :undoc-members:
   :special-members: __init__, __aenter__, __aexit__
   :exclude-members: _serialize, _deserialize, _namespace_key, _remove_namespace

Core Methods
~~~~~~~~~~~~

.. automethod:: src.cache_manager.CacheManager.get
.. automethod:: src.cache_manager.CacheManager.set
.. automethod:: src.cache_manager.CacheManager.delete
.. automethod:: src.cache_manager.CacheManager.clear
.. automethod:: src.cache_manager.CacheManager.close

Batch Operations
~~~~~~~~~~~~~~~~

.. automethod:: src.cache_manager.CacheManager.get_many
.. automethod:: src.cache_manager.CacheManager.set_many

Statistics and Monitoring
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automethod:: src.cache_manager.CacheManager.get_stats

Decorators
~~~~~~~~~~

.. autofunction:: src.cache_manager.cached 
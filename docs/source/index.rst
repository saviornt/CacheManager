.. CacheManager documentation master file, created by
   sphinx-quickstart on Thu Mar 20 03:56:24 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

CacheManager Documentation
==========================

CacheManager is a powerful and flexible caching system for Python applications. It provides a unified interface to various cache backends, offering features like hybrid caching, eviction policies, resilience mechanisms, and more.

Features
--------

* **Multi-layer Caching**: Combine memory, disk, and remote caches for optimal performance
* **Flexible Configuration**: Comprehensive options for all aspects of caching behavior
* **Pluggable Eviction Policies**: LRU, LFU, FIFO, and custom policies
* **Advanced Compression**: Automatically compress cache data to save space
* **Resilience**: Built-in mechanisms for handling failures and recovery
* **Namespacing**: Organize cache data with hierarchical namespaces
* **Security**: Encryption and access control for sensitive cached data
* **Telemetry**: Extensive monitoring and reporting capabilities
* **Cache Warmup**: Strategies for populating cache before it's needed

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   quickstart
   configuration
   api/index
   advanced/index
   examples
   contributing
   changelog

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


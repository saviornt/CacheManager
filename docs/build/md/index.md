<!-- CacheManager documentation master file, created by
sphinx-quickstart on Thu Mar 20 03:56:24 2025.
You can adapt this file completely to your liking, but it should at least
contain the root `toctree` directive. -->

# CacheManager Documentation

CacheManager is a powerful and flexible caching system for Python applications. It provides a unified interface to various cache backends, offering features like hybrid caching, eviction policies, resilience mechanisms, and more.

## Features

* **Multi-layer Caching**: Combine memory, disk, and remote caches for optimal performance
* **Flexible Configuration**: Comprehensive options for all aspects of caching behavior
* **Pluggable Eviction Policies**: LRU, LFU, FIFO, and custom policies
* **Advanced Compression**: Automatically compress cache data to save space
* **Resilience**: Built-in mechanisms for handling failures and recovery
* **Namespacing**: Organize cache data with hierarchical namespaces
* **Security**: Encryption and access control for sensitive cached data
* **Telemetry**: Extensive monitoring and reporting capabilities
* **Cache Warmup**: Strategies for populating cache before it’s needed

## Contents:

* [Installation](installation.md)
  * [Prerequisites](installation.md#prerequisites)
  * [Installing from PyPI](installation.md#installing-from-pypi)
  * [Installing from Source](installation.md#installing-from-source)
  * [Optional Dependencies](installation.md#optional-dependencies)
* [Quickstart](quickstart.md)
  * [Basic Usage](quickstart.md#basic-usage)
  * [Using the Cache Decorator](quickstart.md#using-the-cache-decorator)
  * [Multi-layer Caching](quickstart.md#multi-layer-caching)
* [Configuration](configuration.md)
  * [Basic Configuration](configuration.md#basic-configuration)
  * [Environment Variables](configuration.md#environment-variables)
  * [Multi-layer Caching](configuration.md#multi-layer-caching)
  * [Compression Settings](configuration.md#compression-settings)
  * [Security Settings](configuration.md#security-settings)
  * [Telemetry and Monitoring](configuration.md#telemetry-and-monitoring)
  * [Advanced Features](configuration.md#advanced-features)
  * [Complete Configuration Reference](configuration.md#complete-configuration-reference)
* [API Reference](api/index.md)
  * [Cache Manager](api/cache_manager.md)
  * [Cache Configuration](api/cache_config.md)
  * [Cache Layers](api/cache_layers.md)
  * [Decorators](api/decorators.md)
  * [Eviction Policies](api/eviction_policies.md)
  * [Utilities](api/utils.md)
* [Advanced Features](advanced/index.md)
  * [Hybrid Caching](advanced/hybrid_caching.md)
  * [Eviction Strategies](advanced/eviction_strategies.md)
  * [Compression](advanced/compression.md)
  * [Namespacing](advanced/namespacing.md)
  * [Telemetry](advanced/telemetry.md)
  * [Security](advanced/security.md)
  * [Resilience](advanced/resilience.md)
  * [Bulk Operations](advanced/bulk_operations.md)
  * [Cache Warmup](advanced/cache_warmup.md)
  * [Adaptive TTL](advanced/adaptive_ttl.md)
  * [Distributed Features](advanced/distributed_features.md)
* [Examples](examples.md)
  * [Basic Usage Example](examples.md#basic-usage-example)
  * [Function Result Caching](examples.md#function-result-caching)
  * [Hybrid Caching Example](examples.md#hybrid-caching-example)
  * [Async Usage](examples.md#async-usage)
* [Contributing](contributing.md)
  * [Development Setup](contributing.md#development-setup)
  * [Coding Standards](contributing.md#coding-standards)
  * [Pull Request Process](contributing.md#pull-request-process)
  * [Running Tests](contributing.md#running-tests)
  * [Building Documentation](contributing.md#building-documentation)
* [Changelog](changelog.md)
  * [Version 1.0.0 (2025-03-20)](changelog.md#version-1-0-0-2025-03-20)

# Indices and tables

* [Index](genindex.md)
* [Module Index](py-modindex.md)
* [Search Page](search.md)

# CacheManager

A flexible and extensible caching solution for Python applications supporting multiple cache layers, eviction policies, and advanced features.

## Features

- **Multilayer Caching**: Combine memory, Redis, and disk caching for optimal performance
- **Configurable Eviction Policies**: LRU, LFU, and FIFO implementations
- **Advanced Caching Strategies**:
  - Compression for efficient storage
  - Namespacing for logical separation
  - Telemetry for monitoring cache performance
  - Security features for data protection
  - Resilience mechanisms
- **Decorator-based Caching**: Easily cache function results
- **Bulk Operations**: Efficient handling of multiple cache items
- **Extensive Configuration Options**: Fine-tune cache behavior for your needs

## Installation

```bash
pip install git+https://github.com/saviornt/cachemanager
```

## Quick Start

```python
from src.cache_manager import CacheManager
from src.cache_config import CacheConfig

# Create a cache configuration
config = CacheConfig(
    cache_ttl=300,  # 5 minutes TTL
    eviction_policy='LRU',  # Use Least Recently Used eviction
    memory_cache_enabled=True,  # Enable in-memory caching
    disk_cache_enabled=True,  # Enable disk caching
    cache_dir='./cache'  # Location for disk cache
)

# Initialize cache manager
cache = CacheManager(config)

# Set a value in the cache
cache.set('key1', 'value1')

# Get a value from the cache
value = cache.get('key1')

# Use the caching decorator
@cache.cached()
def expensive_operation(param):
    # Expensive computation here
    return result

# Call the function - result will be cached
result1 = expensive_operation('param1')
result2 = expensive_operation('param1')  # Returns cached result
```

## Documentation

For full documentation, see the [CacheManager Documentation](docs/build/html/index.html).

### Key Topics

- [Installation Guide](docs/build/html/installation.html)
- [Quick Start](docs/build/html/quickstart.html)
- [Configuration Options](docs/build/html/configuration.html)
- [API Reference](docs/build/html/api/index.html)
- [Advanced Features](docs/build/html/advanced/index.html)
- [Examples](docs/build/html/examples.html)

## Advanced Usage

### Hybrid Caching

```python
from src.cache_config import CacheConfig, CacheLayerConfig, CacheLayerType

# Configure multiple cache layers
config = CacheConfig(
    use_layered_cache=True,
    cache_layers=[
        CacheLayerConfig(type=CacheLayerType.MEMORY, ttl=60),  # 1 minute in memory
        CacheLayerConfig(type=CacheLayerType.REDIS, ttl=300),  # 5 minutes in Redis
        CacheLayerConfig(type=CacheLayerType.DISK, ttl=3600)   # 1 hour on disk
    ]
)

# Initialize cache manager with layered caching
cache = CacheManager(config)
```

### Data Compression

```python
# Enable compression for large objects
config = CacheConfig(
    enable_compression=True,
    compression_min_size=1024,  # Compress objects larger than 1KB
    compression_level=6         # Compression level (1-9)
)

cache = CacheManager(config)
```

## Contributing

Contributions are welcome! Please see [Contributing Guide](docs/build/html/contributing.html) for details.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

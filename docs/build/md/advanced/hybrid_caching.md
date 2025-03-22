# Hybrid Caching

Hybrid caching combines multiple cache layers with different performance and persistence characteristics to create an optimal caching system.

## Overview

CacheManager’s hybrid caching combines different storage backends into a unified caching system:

- **Memory Cache**: Fastest access but volatile (lost on restart)
- **Redis Cache**: Shared across instances, moderate speed
- **Disk Cache**: Persistent local storage, slowest but durable

This approach gives you the benefits of each layer while minimizing their drawbacks.

## Configuration

To enable hybrid caching, configure multiple cache layers:

```python
from src.cache_manager import CacheManager
from src.cache_config import CacheConfig, CacheLayerConfig, CacheLayerType

config = CacheConfig(
    use_layered_cache=True,
    cache_layers=[
        CacheLayerConfig(
            type=CacheLayerType.MEMORY,
            ttl=60,
            max_size=1000
        ),
        CacheLayerConfig(
            type=CacheLayerType.REDIS,
            ttl=3600,
            enabled=True
        ),
        CacheLayerConfig(
            type=CacheLayerType.DISK,
            ttl=86400,
            max_size=None  # Use parent setting
        )
    ],
    write_through=True,
    read_through=True
)

cache = CacheManager(config=config)
```

## Key Options

- **use_layered_cache**: Enable hybrid caching
- **cache_layers**: List of layer configurations
- **write_through**: Write to all layers on set operations
- **read_through**: Read from slower layers when item not found in faster layers

## Cache Flow

**Writing (with write_through=True)**:

1. Data is written to all enabled layers
2. Each layer applies its own TTL settings

**Reading (with read_through=True)**:

1. Check memory cache first (fastest)
2. If not found, check Redis cache
3. If not found, check disk cache (slowest)
4. If found in a slower layer, promote to faster layers

## Performance Considerations

- Each additional layer adds overhead to write operations
- Read operations can fall through to slower layers
- Consider setting shorter TTLs for faster layers
- Memory caching helps reduce load on Redis servers

## Example Use Case

Hybrid caching is ideal for scenarios where:

- You need the fastest possible access for frequently used data
- High availability is required even if an application restarts
- Some data should persist longer term, even after restarts
- You want to reduce network traffic to Redis for common operations

## Advanced Configuration

For more advanced configuration options, see the [Cache Configuration](../api/cache_config.md) API reference.

# Eviction Strategies

Cache eviction strategies determine which items are removed from the cache when it reaches capacity limits. CacheManager provides several built-in eviction strategies and allows for custom implementations.

## Built-in Eviction Policies

CacheManager offers the following built-in eviction policies:

### LRU (Least Recently Used)

The LRU policy removes the least recently accessed items first. This strategy works well for most general-purpose caching scenarios.

```python
from src.cache_manager import CacheManager
from src.cache_config import CacheConfig, EvictionPolicy

config = CacheConfig(
    cache_max_size=1000,
    eviction_policy=EvictionPolicy.LRU
)

cache = CacheManager(config=config)
```

### FIFO (First In First Out)

The FIFO policy removes the oldest items first, regardless of how frequently they are accessed. This is useful for time-sensitive data.

```python
config = CacheConfig(
    cache_max_size=1000,
    eviction_policy=EvictionPolicy.FIFO
)
```

### LFU (Least Frequently Used)

The LFU policy removes the least frequently accessed items first. This works best when access patterns have high locality.

```python
config = CacheConfig(
    cache_max_size=1000,
    eviction_policy=EvictionPolicy.LFU
)
```

## Hybrid Eviction Policies

Different cache layers can use different eviction policies:

```python
from src.cache_config import CacheLayerConfig, CacheLayerType

config = CacheConfig(
    use_layered_cache=True,
    cache_layers=[
        CacheLayerConfig(
            type=CacheLayerType.MEMORY,
            max_size=1000,
            eviction_policy=EvictionPolicy.LRU  # Fast memory uses LRU
        ),
        CacheLayerConfig(
            type=CacheLayerType.DISK,
            max_size_bytes=1024*1024*100,  # 100 MB
            eviction_policy=EvictionPolicy.LFU  # Disk uses LFU
        )
    ]
)
```

## Time-Based Eviction

In addition to size-based eviction policies, CacheManager supports time-based expiration:

```python
config = CacheConfig(
    cache_ttl=3600,  # 1 hour TTL
    adaptive_ttl=True  # TTL adjusts based on access patterns
)
```

## Eviction Events

You can register callbacks to be notified when items are evicted:

```python
def on_eviction(key, value, reason):
    print(f"Item with key {key} was evicted. Reason: {reason}")

cache = CacheManager(config=config)
cache.register_eviction_listener(on_eviction)
```

## Implementation Details

CacheManager implements eviction policies efficiently:

- LRU: Uses an ordered dictionary with move-to-end operation (O(1) complexity)
- FIFO: Uses a deque data structure for constant-time operations
- LFU: Uses a frequency counter with a min-heap for efficient minimum finding

For more information on eviction policies and implementation details, see the API reference.

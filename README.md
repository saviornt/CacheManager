# CacheManager

A flexible caching system that supports both local file-based caching (using `shelve`) and Redis-based caching.

## Features

- Async interface for all operations
- Multiple eviction policies:
  - LRU (Least Recently Used) - default
  - FIFO (First In First Out)
  - LFU (Least Frequently Used)
- Namespace support for isolating different parts of the cache
- Layered caching with memory and disk/Redis layers
- Read-through and write-through cache patterns
- Cache compression for efficient storage
- Cache statistics collection (hits, misses, hit rate)
- In-memory cache layer for improved performance
- Configurable TTL (time-to-live) for cache entries
- Seamless switching between local storage and Redis
- Robust error handling with circuit breaker pattern
- Retry mechanism for cache operations
- Bulk operations (get_many, set_many)
- Decorator for easy function result caching

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/cachemanager.git
cd cachemanager

# Install the package in development mode
pip install -e .
```

## Configuration

CacheManager can be configured through environment variables or by passing parameters to the `CacheConfig` constructor:

```python
from src.cache_config import CacheConfig, EvictionPolicy
from src.cache_manager import CacheManager

# Configure through environment variables
# export CACHE_DIR=".cache"
# export CACHE_MAX_SIZE=1000
# export EVICTION_POLICY="lru"  # Options: "lru", "fifo", "lfu"
# export CACHE_NAMESPACE="myapp"
# export USE_REDIS=false

# Or configure directly
config = CacheConfig(
    cache_dir=".cache",
    cache_max_size=1000,
    eviction_policy=EvictionPolicy.LRU,
    namespace="myapp",
    use_redis=False
)

cache = CacheManager(config=config)
```

## Usage

### Basic Operations

```python
import asyncio
from src.cache_manager import CacheManager

async def example():
    # Create a cache manager with default configuration
    cache = CacheManager()
    
    # Store a value
    await cache.set("my_key", {"data": "example"})
    
    # Retrieve a value
    value = await cache.get("my_key")
    print(value)  # {'data': 'example'}
    
    # Store with expiration (seconds)
    await cache.set("temp_key", "temporary", expiration=60)
    
    # Bulk operations
    await cache.set_many({
        "key1": "value1",
        "key2": "value2"
    })
    
    results = await cache.get_many(["key1", "key2"])
    print(results)  # {'key1': 'value1', 'key2': 'value2'}
    
    # Clear the cache
    await cache.clear()
    
    # Close the cache (important for Redis connections)
    await cache.close()
    
    # Or use as an async context manager
    async with CacheManager() as cm:
        await cm.set("context_key", "value")
        val = await cm.get("context_key")
        print(val)  # "value"

# Run the example
asyncio.run(example())
```

### Function Result Caching

Use the cached decorator to automatically cache function results:

```python
from src.cache_manager import CacheManager

cache = CacheManager()

@cache.cached(ttl=60)  # Cache results for 60 seconds
async def fetch_user_data(user_id: int):
    # Expensive operation to fetch user data
    return {"user_id": user_id, "name": "User Name"}
    
# First call executes the function
data1 = await fetch_user_data(123)

# Second call returns cached result
data2 = await fetch_user_data(123)
```

### Using Namespaces

Namespaces allow you to isolate different parts of the cache:

```python
from src.cache_config import CacheConfig
from src.cache_manager import CacheManager

# Create cache managers with different namespaces
user_cache = CacheManager(CacheConfig(namespace="users"))
product_cache = CacheManager(CacheConfig(namespace="products"))

# Keys won't collide even if they have the same name
await user_cache.set("id_123", {"name": "John Doe"})
await product_cache.set("id_123", {"name": "Laptop"})

user = await user_cache.get("id_123")  # {"name": "John Doe"}
product = await product_cache.get("id_123")  # {"name": "Laptop"}
```

## Testing

The package includes a comprehensive test suite. To run the tests:

```bash
# Run all tests
python -m pytest

# Run specific tests using pytest directly
python -m pytest tests/test_cache_manager.py -v

# Run tests with output capturing disabled
python -m pytest tests/test_cache_manager.py -v -s
```

Test results are stored in the `tests/results` directory.

## License

MIT

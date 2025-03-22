# Examples

This page provides practical examples of how to use CacheManager in different scenarios.

## Basic Usage Example

```python
from src.cache_manager import CacheManager
from src.cache_config import CacheConfig

# Create a simple in-memory cache
config = CacheConfig(
    cache_max_size=1000,
    cache_ttl=300,  # 5 minutes
    eviction_policy="lru"
)

cache = CacheManager(config=config)

# Store a value
cache.set("user:1:profile", {"name": "John", "email": "john@example.com"})

# Retrieve the value
profile = cache.get("user:1:profile")
print(profile)  # Output: {"name": "John", "email": "john@example.com"}

# Delete a value
cache.delete("user:1:profile")

# Clear the entire cache
cache.clear()
```

## Function Result Caching

```python
from src.cache_manager import cached
from src.cache_config import CacheConfig
import time

config = CacheConfig(ttl=60)  # Cache results for 60 seconds

@cached(config=config)
def slow_database_query(user_id, filters=None):
    """Simulate a slow database query."""
    print(f"Running slow query for user {user_id} with filters {filters}")
    time.sleep(2)  # Simulate 2-second delay
    return {"results": [1, 2, 3], "user_id": user_id, "filters": filters}

# First call will execute the function
result1 = slow_database_query(42, {"status": "active"})
print("First call completed")

# Second call with same args will return cached result (no 2-second delay)
result2 = slow_database_query(42, {"status": "active"})
print("Second call completed")

# Different args will execute the function again
result3 = slow_database_query(42, {"status": "inactive"})
print("Third call completed")
```

## Hybrid Caching Example

```python
from src.cache_manager import CacheManager
from src.cache_config import CacheConfig
import time

# Create a hybrid cache with memory and disk layers
config = CacheConfig(
    use_layered_cache=True,
    write_through=True,
    read_through=True,
    cache_layers=[
        {"type": "memory", "ttl": 60},       # Fast but volatile
        {"type": "disk", "ttl": 86400}       # Slower but persistent
    ]
)

cache = CacheManager(config=config)

# Store a value
cache.set("key1", "value1")

# Accessing from memory (fast)
start = time.time()
value = cache.get("key1")
print(f"Read from hybrid cache: {value} in {time.time() - start:.6f} seconds")

# Simulate application restart (memory cache cleared)
# In real app this would be a new process, here we just create a new cache
config2 = CacheConfig(
    use_layered_cache=True,
    write_through=True,
    read_through=True,
    cache_layers=[
        {"type": "memory", "ttl": 60},
        {"type": "disk", "ttl": 86400}
    ]
)

cache2 = CacheManager(config=config2)

# Value will be loaded from disk (slower but still available)
start = time.time()
value = cache2.get("key1")
print(f"Read after 'restart': {value} in {time.time() - start:.6f} seconds")
```

## Async Usage

```python
import asyncio
from src.cache_manager import CacheManager
from src.cache_config import CacheConfig

async def main():
    # Create a cache instance with async support
    config = CacheConfig(use_redis=True)

    async with CacheManager(config=config) as cache:
        # Store a value
        await cache.set("key1", "value1")

        # Retrieve the value
        value = await cache.get("key1")
        print(f"Retrieved value: {value}")

        # Batch operations
        await cache.set_many({
            "batch1": "value1",
            "batch2": "value2",
            "batch3": "value3"
        })

        # Get multiple values at once
        results = await cache.get_many(["batch1", "batch2", "batch3"])
        print(f"Batch results: {results}")

# Run the async example
if __name__ == "__main__":
    asyncio.run(main())
```

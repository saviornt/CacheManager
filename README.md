# CacheManager

A flexible caching system that supports both local file-based caching (using `shelve`) and Redis-based caching.

## Features

- Async interface for all operations
- LRU eviction policy for cache size management
- Configurable TTL (time-to-live) for cache entries
- Seamless switching between local storage and Redis
- Retry mechanism for cache operations

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
from src.cache_config import CacheConfig
from src.cache_manager import CacheManager

# Configure through environment variables
# export CACHE_DIR=".cache"
# export CACHE_MAX_SIZE=1000
# export USE_REDIS=false

# Or configure directly
config = CacheConfig(
    cache_dir=".cache",
    cache_max_size=1000,
    use_redis=False
)

cache = CacheManager(config=config)
```

## Usage

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

## Testing

The package includes a comprehensive test suite. To run the tests:

```bash
# Run tests with detailed output
python run_tests.py

# Or run specific tests using pytest directly
python -m pytest tests/test_cache_manager.py -v

# Run tests with output capturing disabled
python -m pytest tests/test_cache_manager.py -v -s
```

Test results are stored in the `test_results` directory.

## License

MIT

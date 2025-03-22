# Bulk Operations

CacheManager supports efficient bulk operations for getting, setting, and deleting multiple cache items in a single call.

## Overview

This section covers the bulk operations features of CacheManager.

## Basic Usage

```python
from src.cache_manager import CacheManager
from src.cache_config import CacheConfig

config = CacheConfig(
    # bulk operations configuration
)

cache = CacheManager(config=config)
```

## Configuration Options

For detailed configuration options, see the [Cache Configuration](../api/cache_config.md) API reference.

## Advanced Usage

For more advanced bulk operations scenarios, refer to the code examples and API documentation.

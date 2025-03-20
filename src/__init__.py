"""CacheManager package for efficient caching with multiple backends."""

from .cache_config import CacheConfig
from .cache_manager import CacheManager

__all__ = ["CacheManager", "CacheConfig"]

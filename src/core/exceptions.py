"""Exception classes for CacheManager."""

class CacheError(Exception):
    """Base exception class for all cache-related errors."""
    pass

class CacheConnectionError(CacheError):
    """Exception raised when there's an error connecting to the cache backend."""
    pass

class CacheSerializationError(CacheError):
    """Exception raised when there's an error serializing or deserializing data."""
    pass

class CacheKeyError(CacheError):
    """Exception raised when there's an error with the key."""
    pass

class CacheStorageError(CacheError):
    """Exception raised when there's an error with the storage backend."""
    pass 
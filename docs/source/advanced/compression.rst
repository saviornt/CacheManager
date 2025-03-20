Compression
===========

CacheManager includes built-in compression capabilities to reduce memory usage and storage requirements for cached data.

Overview
--------

Data compression is particularly useful for:

- Reducing memory usage for large cached objects
- Decreasing network transfer times for distributed caches
- Lowering disk storage requirements for persistent caches

Configuration
-------------

To enable compression in CacheManager:

.. code-block:: python

    from src.cache_manager import CacheManager
    from src.cache_config import CacheConfig
    
    config = CacheConfig(
        enable_compression=True,
        compression_min_size=1024,  # Only compress items larger than 1KB
        compression_level=6         # Compression level (1-9, higher = more compression)
    )
    
    cache = CacheManager(config=config)

Compression Algorithms
----------------------

CacheManager supports multiple compression algorithms:

ZLIB (Default)
~~~~~~~~~~~~~~

A general-purpose compression algorithm with good balance of speed and compression ratio.

.. code-block:: python

    config = CacheConfig(
        enable_compression=True,
        compression_algorithm="zlib"
    )

GZIP
~~~~

Similar to ZLIB but with a different header format. Useful when you need gzip compatibility.

.. code-block:: python

    config = CacheConfig(
        enable_compression=True,
        compression_algorithm="gzip"
    )

BROTLI
~~~~~~

Offers higher compression ratios but might be slower. Best for disk caching.

.. code-block:: python

    config = CacheConfig(
        enable_compression=True,
        compression_algorithm="brotli",
        compression_level=5  # Brotli levels 0-11
    )

LZMA
~~~~

Highest compression ratio but slowest. Best for rarely accessed but very large data.

.. code-block:: python

    config = CacheConfig(
        enable_compression=True,
        compression_algorithm="lzma"
    )

Selective Compression
---------------------

CacheManager can selectively compress items based on size:

.. code-block:: python

    config = CacheConfig(
        enable_compression=True,
        compression_min_size=5120,  # Only compress items larger than 5KB
    )

Layer-Specific Compression
--------------------------

Different compression settings can be applied to different cache layers:

.. code-block:: python

    from src.cache_config import CacheLayerConfig, CacheLayerType
    
    config = CacheConfig(
        use_layered_cache=True,
        cache_layers=[
            CacheLayerConfig(
                type=CacheLayerType.MEMORY,
                enable_compression=False  # No compression for memory layer
            ),
            CacheLayerConfig(
                type=CacheLayerType.DISK,
                enable_compression=True,
                compression_algorithm="lzma",  # Higher compression for disk
                compression_level=9
            )
        ]
    )

Performance Considerations
--------------------------

- Compression adds CPU overhead for both storing and retrieving items
- For small items, compression overhead might exceed benefits
- Higher compression levels increase CPU usage but reduce storage requirements
- Consider using different compression settings for different cache layers

Implementation Details
----------------------

Under the hood, CacheManager uses Python's standard libraries (zlib, gzip, brotli, lzma) 
for compression. The compression is transparent to the user; you don't need to manually 
decompress when retrieving items from the cache. 
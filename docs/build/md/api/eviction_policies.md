# Eviction Policies

Eviction policies determine which items are removed from the cache when it reaches capacity.

### *class* src.cache_config.EvictionPolicy(\*values)

Enum defining cache eviction policies.

Available policies:
- LRU: Least Recently Used - evicts least recently accessed items first
- FIFO: First In First Out - evicts oldest items first
- LFU: Least Frequently Used - evicts least frequently accessed items

#### LRU *= 'lru'*

#### FIFO *= 'fifo'*

#### LFU *= 'lfu'*

## LRU (Least Recently Used)

The LRU policy removes the least recently used items first. This is the default policy and works well for most workloads.

## FIFO (First In First Out)

The FIFO policy removes the oldest items first, regardless of how frequently they are accessed.

## LFU (Least Frequently Used)

The LFU policy removes the least frequently accessed items first. This works well when certain items are accessed much more frequently than others.

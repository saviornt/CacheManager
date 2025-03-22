Eviction Policies
=================

.. automodule:: src.cache_config
   :members: EvictionPolicy
   :undoc-members:
   :show-inheritance:
   :no-index:

LRU (Least Recently Used)
-------------------------

The LRU policy removes the least recently used items first. This is the default policy and works well for most workloads.

FIFO (First In First Out)
-------------------------

The FIFO policy removes the oldest items first, regardless of how frequently they are accessed.

LFU (Least Frequently Used)
---------------------------

The LFU policy removes the least frequently accessed items first. This works well when certain items are accessed much more frequently than others. 
"""Adaptive TTL functionality for CacheManager.

This module provides mechanisms to adjust cache TTL values dynamically
based on access patterns, improving cache efficiency.
"""

import time
import logging
import math
from typing import Dict, List, Optional, Any, Tuple, Set
from collections import Counter, defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

class AdaptiveTTLManager:
    """Manages adaptive TTL adjustments based on access patterns.
    
    This class tracks key accesses and adjusts TTL values accordingly:
    - Frequently accessed keys get longer TTLs to reduce recomputation
    - Rarely accessed keys get shorter TTLs to save memory
    """
    
    def __init__(
        self,
        enabled: bool = False,
        min_ttl: int = 60,  # Minimum TTL in seconds
        max_ttl: int = 86400,  # Maximum TTL in seconds (1 day)
        access_count_threshold: int = 10,  # Number of accesses before adjusting TTL
        adjustment_factor: float = 1.5,  # Multiplicative factor for TTL adjustments
        decay_factor: float = 0.9,  # Decay factor for access counts over time
        decay_interval: int = 3600,  # How often to apply decay (in seconds)
        ttl_bands: Optional[List[int]] = None  # Discrete TTL values to use
    ):
        """Initialize the adaptive TTL manager.
        
        Args:
            enabled: Whether adaptive TTL is enabled
            min_ttl: Minimum TTL value in seconds
            max_ttl: Maximum TTL value in seconds
            access_count_threshold: Number of accesses before TTL adjustment
            adjustment_factor: How much to adjust TTL by each time
            decay_factor: Factor to decay access counts over time
            decay_interval: How often to apply decay (in seconds)
            ttl_bands: Optional list of discrete TTL values to use instead of continuous
        """
        self.enabled = enabled
        self._min_ttl = min_ttl
        self._max_ttl = max_ttl
        self._access_threshold = access_count_threshold
        self._adjustment_factor = adjustment_factor
        self._decay_factor = decay_factor
        self._decay_interval = decay_interval
        self._ttl_bands = sorted(ttl_bands) if ttl_bands else None
        
        # Track access counts for each key
        self._access_counts: Dict[str, int] = Counter()
        # Track current TTL for each key
        self._current_ttls: Dict[str, int] = {}
        # Track last access time for each key
        self._last_access: Dict[str, float] = {}
        # Track when keys were first seen
        self._first_seen: Dict[str, float] = {}
        # Track when we last decayed counts
        self._last_decay_time = time.time()
        # Statistics
        self._adjustment_counts = {
            'increased': 0,
            'decreased': 0,
            'unchanged': 0
        }
    
    def record_access(self, key: str) -> None:
        """Record a cache access for a key.
        
        Args:
            key: Cache key that was accessed
        """
        if not self.enabled:
            return
            
        now = time.time()
        
        # Record first time seeing this key
        if key not in self._first_seen:
            self._first_seen[key] = now
            
        # Update access count and timestamp
        self._access_counts[key] += 1
        self._last_access[key] = now
        
        # Check if we should apply decay
        if now - self._last_decay_time > self._decay_interval:
            self._apply_decay()
            self._last_decay_time = now
    
    def get_ttl(self, key: str, default_ttl: int) -> int:
        """Get the adaptive TTL for a key.
        
        Args:
            key: Cache key
            default_ttl: Default TTL to use if no adaptation needed
            
        Returns:
            int: Adjusted TTL in seconds
        """
        if not self.enabled:
            return default_ttl
            
        # If we haven't seen this key before, use default
        if key not in self._access_counts:
            return default_ttl
            
        # If we've already calculated a TTL for this key, use that
        if key in self._current_ttls:
            return self._current_ttls[key]
            
        # Otherwise, use default for now
        return default_ttl
    
    def adjust_ttl(self, key: str, default_ttl: int) -> int:
        """Adjust TTL based on access patterns.
        
        This is called when we're about to set a key in the cache.
        
        Args:
            key: Cache key
            default_ttl: Default TTL to adjust from
            
        Returns:
            int: Adjusted TTL in seconds
        """
        if not self.enabled:
            return default_ttl
            
        # Record access
        self.record_access(key)
        
        # Only adjust if we've seen enough accesses
        if self._access_counts[key] < self._access_threshold:
            return default_ttl
            
        # Get current TTL or use default
        current_ttl = self._current_ttls.get(key, default_ttl)
        
        # Calculate access rate (accesses per hour)
        now = time.time()
        first_seen = self._first_seen.get(key, now)
        hours_since_first_seen = max(1, (now - first_seen) / 3600)
        access_rate = self._access_counts[key] / hours_since_first_seen
        
        # Calculate TTL adjustment based on access rate
        if access_rate > 10:  # High access rate (>10/hour)
            new_ttl = int(current_ttl * self._adjustment_factor)
            self._adjustment_counts['increased'] += 1
        elif access_rate < 1:  # Low access rate (<1/hour)
            new_ttl = int(current_ttl / self._adjustment_factor)
            self._adjustment_counts['decreased'] += 1
        else:
            new_ttl = current_ttl
            self._adjustment_counts['unchanged'] += 1
        
        # Enforce min/max TTL
        new_ttl = max(self._min_ttl, min(self._max_ttl, new_ttl))
        
        # Use TTL bands if configured
        if self._ttl_bands:
            new_ttl = self._get_nearest_band(new_ttl)
            
        # Update stored TTL
        self._current_ttls[key] = new_ttl
        
        logger.debug(
            f"Adjusted TTL for key {key}: {current_ttl}s -> {new_ttl}s "
            f"(access rate: {access_rate:.2f}/hour, count: {self._access_counts[key]})"
        )
        
        return new_ttl
    
    def _get_nearest_band(self, ttl: int) -> int:
        """Get the nearest TTL band value.
        
        Args:
            ttl: TTL value
            
        Returns:
            int: Nearest value from ttl_bands
        """
        if not self._ttl_bands:
            return ttl
            
        # Find closest band
        if ttl <= self._ttl_bands[0]:
            return self._ttl_bands[0]
            
        if ttl >= self._ttl_bands[-1]:
            return self._ttl_bands[-1]
            
        # Binary search for the right band
        low, high = 0, len(self._ttl_bands) - 1
        while low <= high:
            mid = (low + high) // 2
            if self._ttl_bands[mid] < ttl:
                low = mid + 1
            else:
                high = mid - 1
                
        # Choose the closer of the two bands
        if low < len(self._ttl_bands) and high >= 0:
            if ttl - self._ttl_bands[high] < self._ttl_bands[low] - ttl:
                return self._ttl_bands[high]
            return self._ttl_bands[low]
        elif low < len(self._ttl_bands):
            return self._ttl_bands[low]
        else:
            return self._ttl_bands[high]
    
    def _apply_decay(self) -> None:
        """Decay access counts over time to focus on recent patterns."""
        if not self.enabled:
            return
            
        # Apply decay to all counts
        for key in list(self._access_counts.keys()):
            self._access_counts[key] = max(1, int(self._access_counts[key] * self._decay_factor))
            
            # Garbage collect keys with very low counts that haven't been accessed recently
            if (self._access_counts[key] <= 1 and 
                time.time() - self._last_access.get(key, 0) > self._decay_interval * 10):
                del self._access_counts[key]
                if key in self._current_ttls:
                    del self._current_ttls[key]
                if key in self._last_access:
                    del self._last_access[key]
                if key in self._first_seen:
                    del self._first_seen[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about adaptive TTL adjustments.
        
        Returns:
            Dict containing statistics
        """
        return {
            'enabled': self.enabled,
            'keys_tracked': len(self._access_counts),
            'adjustments': self._adjustment_counts.copy(),
            'ttl_distribution': self._get_ttl_distribution(),
            'last_decay': datetime.fromtimestamp(self._last_decay_time).isoformat(),
            'top_accessed_keys': self._get_top_accessed_keys(10),
            'config': {
                'min_ttl': self._min_ttl,
                'max_ttl': self._max_ttl,
                'access_threshold': self._access_threshold,
                'adjustment_factor': self._adjustment_factor,
                'decay_factor': self._decay_factor,
                'decay_interval': self._decay_interval,
                'ttl_bands': self._ttl_bands
            }
        }
    
    def _get_ttl_distribution(self) -> Dict[str, int]:
        """Get distribution of current TTL values.
        
        Returns:
            Dict mapping TTL ranges to counts
        """
        if not self._current_ttls:
            return {}
            
        # Define TTL buckets (in seconds)
        buckets = [
            (0, 60),         # 0-1 minute
            (60, 300),       # 1-5 minutes
            (300, 900),      # 5-15 minutes
            (900, 3600),     # 15-60 minutes
            (3600, 14400),   # 1-4 hours
            (14400, 86400),  # 4-24 hours
            (86400, float('inf'))  # >1 day
        ]
        
        bucket_labels = [
            "0-1 min",
            "1-5 min",
            "5-15 min",
            "15-60 min",
            "1-4 hours",
            "4-24 hours",
            ">1 day"
        ]
        
        # Count TTLs in each bucket
        distribution = defaultdict(int)
        for ttl in self._current_ttls.values():
            for i, (low, high) in enumerate(buckets):
                if low <= ttl < high:
                    distribution[bucket_labels[i]] += 1
                    break
        
        return dict(distribution)
    
    def _get_top_accessed_keys(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get the most frequently accessed keys.
        
        Args:
            limit: Maximum number of keys to return
            
        Returns:
            List of (key, access_count) tuples
        """
        return self._access_counts.most_common(limit)
    
    def cleanup(self) -> None:
        """Clean up data for keys no longer in the cache."""
        # This would be called periodically with a list of keys still in the cache
        # to remove tracking data for keys that have been evicted
        pass 
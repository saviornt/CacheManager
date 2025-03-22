"""Cache warmup functionality for CacheManager.

This module provides tools for warming up the cache by pre-populating it with
frequently used keys or data sets.
"""

import os
import json
import logging
import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

class CacheWarmup:
    """Handles warming up of the cache.
    
    Provides functionality to pre-populate the cache with frequently used data
    to improve performance on startup or at scheduled intervals.
    """
    
    def __init__(
        self,
        enabled: bool = False,
        warmup_keys_file: Optional[str] = None,
        key_providers: Optional[List[Callable[[], List[str]]]] = None,
        value_providers: Optional[Dict[str, Callable[[], Any]]] = None
    ):
        """Initialize cache warmup.
        
        Args:
            enabled: Whether warmup is enabled
            warmup_keys_file: Path to a JSON file containing keys to warm up
            key_providers: List of functions that return keys to warm up
            value_providers: Dict mapping patterns to functions that return values
        """
        self.enabled = enabled
        self.warmup_keys_file = warmup_keys_file
        self._key_providers = key_providers or []
        self._value_providers = value_providers or {}
        self._is_warming_up = False
        self._warmup_stats: Dict[str, Any] = {
            'last_warmup': None,
            'duration': 0,
            'keys_processed': 0,
            'errors': 0,
            'skipped': 0
        }
    
    async def warmup(self, cache_manager: Any) -> Dict[str, Any]:
        """Warm up the cache by pre-loading keys.
        
        Args:
            cache_manager: The CacheManager instance to use for warming up
            
        Returns:
            Dict: Statistics about the warmup process
        """
        if not self.enabled:
            return {"success": False, "reason": "Cache warmup is disabled"}
            
        if not self.warmup_keys_file:
            return {"success": False, "reason": "No warmup keys file specified"}
            
        logger.info(f"Starting cache warmup with {len(self._value_providers)} keys")
        
        stats = {
            "total_keys": 0,
            "loaded_keys": 0,
            "errors": 0,
            "skipped": 0,
            "time_taken": 0
        }
        
        start_time = time.time()
        
        try:
            # Load keys from file
            with open(self.warmup_keys_file, 'r') as f:
                warmup_data = json.load(f)
                
            # Get list of keys to warm up
            if "keys" in warmup_data:
                keys = warmup_data["keys"]
                stats["total_keys"] = len(keys)
                
                # Process each key
                for key in keys:
                    try:
                        # Check if we have a value provider for this key
                        if key in self._value_providers:
                            # Get value from provider
                            provider = self._value_providers[key]
                            if callable(provider):
                                value = provider()
                                # Set in cache
                                await cache_manager.set(key, value)
                                stats["loaded_keys"] += 1
                            else:
                                # Static value
                                await cache_manager.set(key, provider)
                                stats["loaded_keys"] += 1
                        else:
                            # No value provider, can't warm up this key
                            stats["skipped"] += 1
                    except Exception as e:
                        logger.error(f"Error warming up key {key}: {e}")
                        stats["errors"] += 1
            
        except Exception as e:
            logger.error(f"Error during cache warmup: {e}")
            stats["success"] = False
            stats["reason"] = str(e)
            return stats
            
        # Calculate time taken
        stats["time_taken"] = time.time() - start_time
        stats["success"] = True
        
        logger.info(f"Cache warmup completed in {stats['time_taken']:.2f}s: "
                  f"{stats['loaded_keys']}/{stats['total_keys']} keys loaded, "
                  f"{stats['errors']} errors, {stats['skipped']} skipped")
                  
        return stats
    
    async def _warmup_key(self, cache_obj: Any, key: str, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
        """Warm up a single key in the cache.
        
        Args:
            cache_obj: The cache manager instance
            key: The key to warm up
            semaphore: Semaphore for concurrency control
            
        Returns:
            Dict with information about the operation
        """
        result = {
            'key': key,
            'loaded': False,
            'skipped': False,
            'error': None
        }
        
        async with semaphore:
            try:
                # First check if the key is already in the cache
                existing = await cache_obj.get(key)
                
                if existing is not None:
                    # Key already in cache, skip
                    result['skipped'] = True
                    return result
                
                # Check if we have a value provider for this key
                value = None
                for pattern, provider in self._value_providers.items():
                    if self._match_pattern(pattern, key):
                        try:
                            value = provider()
                            break
                        except Exception as e:
                            logger.error(f"Error getting value for key {key} from provider: {e}")
                            result['error'] = str(e)
                
                # If we have a value, set it in the cache
                if value is not None:
                    await cache_obj.set(key, value)
                    result['loaded'] = True
                else:
                    # No value provider found, try loading from backend (read-through)
                    # This is a no-op if read-through isn't configured properly
                    await cache_obj.get(key)
                    # Check if it got loaded
                    value = await cache_obj.get(key)
                    result['loaded'] = value is not None
                
                return result
                
            except Exception as e:
                logger.error(f"Error warming up key {key}: {e}")
                result['error'] = str(e)
                return result
    
    def _match_pattern(self, pattern: str, key: str) -> bool:
        """Match a key against a pattern.
        
        Args:
            pattern: Glob pattern
            key: Cache key
            
        Returns:
            bool: True if pattern matches key
        """
        if pattern == '*':
            return True
            
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return key.startswith(prefix)
            
        if pattern.startswith('*'):
            suffix = pattern[1:]
            return key.endswith(suffix)
            
        if '*' in pattern:
            parts = pattern.split('*')
            if key.startswith(parts[0]) and key.endswith(parts[-1]):
                return True
                
        return pattern == key
    
    def add_key_provider(self, provider: Callable[[], List[str]]) -> None:
        """Add a function that provides keys for warmup.
        
        Args:
            provider: Function that returns a list of keys
        """
        if provider not in self._key_providers:
            self._key_providers.append(provider)
    
    def add_value_provider(self, pattern: str, provider: Callable[[], Any]) -> None:
        """Add a function that provides values for a key pattern.
        
        Args:
            pattern: Key pattern (glob)
            provider: Function that returns the value for matching keys
        """
        self._value_providers[pattern] = provider
    
    def save_hot_keys(self, keys: List[str], file_path: Optional[str] = None) -> None:
        """Save frequently accessed keys to a file for future warmup.
        
        Args:
            keys: List of hot keys
            file_path: Path to save keys to (defaults to warmup_keys_file)
        """
        if not self.enabled:
            return
            
        path = file_path or self.warmup_keys_file
        if not path:
            logger.warning("No file path specified for saving hot keys")
            return
            
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            
            # Save keys to file
            with open(path, 'w') as f:
                json.dump({
                    'keys': keys,
                    'timestamp': datetime.now().isoformat(),
                    'count': len(keys)
                }, f, indent=2)
                
            logger.info(f"Saved {len(keys)} hot keys to {path}")
            
        except Exception as e:
            logger.error(f"Error saving hot keys to {path}: {e}")
    
    def get_warmup_stats(self) -> Dict[str, Any]:
        """Get statistics about the warmup process.
        
        Returns:
            Dict with warmup statistics
        """
        return self._warmup_stats.copy()
    
    def load_warmup_keys(self) -> List[Dict[str, Any]]:
        """Load warmup keys from the configured file.
        
        Returns:
            List[Dict[str, Any]]: List of key-value pairs to cache
        """
        if not self.enabled or not self.warmup_keys_file:
            return []
            
        try:
            with open(self.warmup_keys_file, 'r') as f:
                data = json.load(f)
                
            # Handle both list and dict formats
            if isinstance(data, dict):
                # Convert dict to list of key-value pairs
                return [{"key": k, "value": v} for k, v in data.items()]
            elif isinstance(data, list):
                # Ensure each item has key and value properties
                result = []
                for item in data:
                    if isinstance(item, dict) and "key" in item and "value" in item:
                        result.append(item)
                    elif isinstance(item, dict):
                        # Skip items that don't have the right structure
                        logger.warning(f"Skipping malformed warmup item: {item}")
                return result
            else:
                logger.error(f"Unexpected data format in warmup file: {type(data)}")
                return []
                
        except Exception as e:
            logger.error(f"Error loading warmup keys file {self.warmup_keys_file}: {e}")
            return [] 
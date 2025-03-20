"""Cache warmup functionality for CacheManager.

This module provides tools for warming up the cache by pre-populating it with
frequently used keys or data sets.
"""

import os
import json
import logging
import asyncio
import time
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
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
    
    async def warmup(
        self,
        cache_obj: Any,
        keys: Optional[List[str]] = None,
        patterns: Optional[List[str]] = None,
        max_concurrent: int = 10,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """Perform cache warmup by pre-populating keys.
        
        Args:
            cache_obj: The cache manager instance to populate
            keys: Optional list of specific keys to warm up
            patterns: Optional list of key patterns to warm up
            max_concurrent: Maximum number of concurrent warmup operations
            timeout: Maximum time in seconds for the warmup process
            
        Returns:
            Dict with statistics about the warmup process
        """
        if not self.enabled:
            logger.info("Cache warmup is disabled")
            return self._warmup_stats
            
        if self._is_warming_up:
            logger.warning("Cache warmup already in progress, skipping")
            return self._warmup_stats
            
        self._is_warming_up = True
        start_time = time.time()
        
        try:
            # Track statistics
            stats = {
                'start_time': datetime.now().isoformat(),
                'keys_processed': 0,
                'keys_loaded': 0,
                'errors': 0,
                'skipped': 0
            }
            
            # Collect keys from all sources
            all_keys = set()
            
            # 1. From explicit keys parameter
            if keys:
                all_keys.update(keys)
            
            # 2. From key providers
            for provider in self._key_providers:
                try:
                    provider_keys = provider()
                    all_keys.update(provider_keys)
                    logger.debug(f"Added {len(provider_keys)} keys from provider {provider.__name__}")
                except Exception as e:
                    logger.error(f"Error getting keys from provider {provider.__name__}: {e}")
                    stats['errors'] += 1
            
            # 3. From warmup keys file
            if self.warmup_keys_file and os.path.exists(self.warmup_keys_file):
                try:
                    warmup_keys = self.load_warmup_keys()
                    for item in warmup_keys:
                        all_keys.add(item['key'])
                    logger.debug(f"Added {len(all_keys)} keys from warmup file")
                except Exception as e:
                    logger.error(f"Error loading warmup keys file {self.warmup_keys_file}: {e}")
                    stats['errors'] += 1
            
            logger.info(f"Starting cache warmup with {len(all_keys)} keys")
            
            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(max_concurrent)
            
            # Create tasks for warmup
            tasks = []
            for key in all_keys:
                task = self._warmup_key(cache_obj, key, semaphore)
                tasks.append(task)
            
            # Wait for all tasks with timeout
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    stats['errors'] += 1
                    logger.error(f"Error warming up key: {result}")
                elif isinstance(result, dict):
                    stats['keys_processed'] += 1
                    if result.get('loaded'):
                        stats['keys_loaded'] += 1
                    if result.get('skipped'):
                        stats['skipped'] += 1
            
            duration = time.time() - start_time
            stats['duration'] = duration
            stats['end_time'] = datetime.now().isoformat()
            
            logger.info(
                f"Cache warmup completed in {duration:.2f}s: "
                f"{stats['keys_loaded']}/{stats['keys_processed']} keys loaded, "
                f"{stats['errors']} errors, {stats['skipped']} skipped"
            )
            
            # Update overall stats
            self._warmup_stats = {
                'last_warmup': stats['start_time'],
                'duration': stats['duration'],
                'keys_processed': stats['keys_processed'],
                'keys_loaded': stats['keys_loaded'],
                'errors': stats['errors'],
                'skipped': stats['skipped']
            }
            
            return stats
            
        finally:
            self._is_warming_up = False
    
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
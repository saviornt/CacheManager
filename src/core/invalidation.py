"""Cross-node cache invalidation for CacheManager.

This module provides functionality for invalidating cache entries across
multiple nodes or instances of CacheManager.
"""

import json
import logging
import asyncio
import time
from typing import Dict, List, Set, Optional, Any, Callable, Awaitable
from enum import Enum
from datetime import datetime

import redis.asyncio as redis
from redis.exceptions import RedisError

from .exceptions import CacheError

logger = logging.getLogger(__name__)

class InvalidationError(CacheError):
    """Exception raised when there's an error with cache invalidation."""
    pass

class InvalidationEvent(str, Enum):
    """Types of cache invalidation events."""
    KEY = "key"  # Invalidate a specific key
    PATTERN = "pattern"  # Invalidate keys matching a pattern
    NAMESPACE = "namespace"  # Invalidate an entire namespace
    ALL = "all"  # Invalidate all cached data

class InvalidationManager:
    """Manages cache invalidation across multiple nodes.
    
    Uses Redis pub/sub to coordinate cache invalidation between
    different instances of CacheManager.
    """
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        channel: str = "cache:invalidation",
        enabled: bool = False,
        node_id: Optional[str] = None
    ):
        """Initialize the invalidation manager.
        
        Args:
            redis_client: Redis client for pub/sub communication
            channel: Redis channel for invalidation messages
            enabled: Whether invalidation is enabled
            node_id: Unique identifier for this cache node
        """
        self.enabled = enabled
        self._redis = redis_client
        self._channel = channel
        self._node_id = node_id or str(time.time())
        self._pubsub = None
        self._listener_task = None
        self._callbacks: Dict[InvalidationEvent, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {
            event: [] for event in InvalidationEvent
        }
        self._last_events: List[Dict[str, Any]] = []
        self._max_event_history = 100
    
    async def start(self) -> None:
        """Start listening for invalidation events.
        
        Raises:
            InvalidationError: If there's an error starting the listener
        """
        if not self.enabled or self._redis is None:
            logger.debug("Invalidation manager is disabled or no Redis client")
            return
            
        try:
            # Create a pub/sub connection
            self._pubsub = self._redis.pubsub()
            
            # Subscribe to the invalidation channel
            await self._pubsub.subscribe(self._channel)
            
            # Start the listener task
            self._listener_task = asyncio.create_task(self._listen_for_events())
            
            logger.info(f"Cache invalidation listener started on channel {self._channel}")
        except RedisError as e:
            logger.error(f"Failed to start invalidation listener: {e}")
            raise InvalidationError(f"Failed to start invalidation listener: {e}") from e
        except Exception as e:
            logger.error(f"Error starting invalidation listener: {e}")
            raise InvalidationError(f"Error starting invalidation listener: {e}") from e
    
    async def stop(self) -> None:
        """Stop listening for invalidation events."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
            
        if self._pubsub:
            await self._pubsub.unsubscribe(self._channel)
            await self._pubsub.close()
            self._pubsub = None
            
        logger.info("Cache invalidation listener stopped")
    
    async def _listen_for_events(self) -> None:
        """Listen for and process invalidation events."""
        if not self._pubsub:
            return
            
        try:
            while True:
                message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                
                if message is None:
                    await asyncio.sleep(0.1)
                    continue
                    
                try:
                    # Process the message
                    await self._process_message(message)
                except Exception as e:
                    logger.error(f"Error processing invalidation message: {e}")
        except asyncio.CancelledError:
            logger.debug("Invalidation listener task cancelled")
            raise
        except Exception as e:
            logger.error(f"Invalidation listener error: {e}")
            # Try to restart the listener
            asyncio.create_task(self._restart_listener())
    
    async def _restart_listener(self) -> None:
        """Attempt to restart the invalidation listener after an error."""
        await asyncio.sleep(5)  # Wait a bit before reconnecting
        try:
            await self.stop()
            await self.start()
        except Exception as e:
            logger.error(f"Failed to restart invalidation listener: {e}")
    
    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Process an invalidation message.
        
        Args:
            message: Redis pub/sub message
        """
        try:
            # Skip non-data messages
            if message['type'] != 'message':
                return
                
            # Parse the message data
            data = json.loads(message['data'])
            
            # Skip messages from this node
            if data.get('node_id') == self._node_id:
                return
                
            # Add to event history
            self._last_events.append(data)
            if len(self._last_events) > self._max_event_history:
                self._last_events = self._last_events[-self._max_event_history:]
                
            # Get the event type
            event_type = InvalidationEvent(data.get('type', 'key'))
            
            # Call the appropriate callbacks
            for callback in self._callbacks.get(event_type, []):
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"Error in invalidation callback: {e}")
                    
            # Always call the ALL event callbacks
            for callback in self._callbacks.get(InvalidationEvent.ALL, []):
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"Error in ALL invalidation callback: {e}")
                    
        except json.JSONDecodeError:
            logger.error("Invalid JSON in invalidation message")
        except Exception as e:
            logger.error(f"Error processing invalidation message: {e}")
    
    def add_callback(
        self, 
        event_type: InvalidationEvent, 
        callback: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Add a callback for a specific invalidation event type.
        
        Args:
            event_type: Type of event to listen for
            callback: Async function to call when event occurs
        """
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
            
        if callback not in self._callbacks[event_type]:
            self._callbacks[event_type].append(callback)
    
    def remove_callback(
        self, 
        event_type: InvalidationEvent, 
        callback: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Remove a callback for a specific invalidation event type.
        
        Args:
            event_type: Type of event
            callback: Function to remove
        """
        if event_type in self._callbacks and callback in self._callbacks[event_type]:
            self._callbacks[event_type].remove(callback)
    
    async def invalidate_key(self, key: str, reason: Optional[str] = None) -> None:
        """Invalidate a specific cache key across all nodes.
        
        Args:
            key: Cache key to invalidate
            reason: Optional reason for invalidation
            
        Raises:
            InvalidationError: If there's an error publishing the event
        """
        if not self.enabled or self._redis is None:
            return
            
        event = {
            'type': InvalidationEvent.KEY.value,
            'key': key,
            'timestamp': datetime.now().isoformat(),
            'node_id': self._node_id,
            'reason': reason
        }
        
        try:
            # Publish the invalidation event
            await self._redis.publish(self._channel, json.dumps(event))
            logger.debug(f"Published invalidation for key: {key}")
        except RedisError as e:
            logger.error(f"Failed to publish key invalidation: {e}")
            raise InvalidationError(f"Failed to publish key invalidation: {e}") from e
    
    async def invalidate_pattern(self, pattern: str, reason: Optional[str] = None) -> None:
        """Invalidate all cache keys matching a pattern.
        
        Args:
            pattern: Key pattern to invalidate (glob-style)
            reason: Optional reason for invalidation
            
        Raises:
            InvalidationError: If there's an error publishing the event
        """
        if not self.enabled or self._redis is None:
            return
            
        event = {
            'type': InvalidationEvent.PATTERN.value,
            'pattern': pattern,
            'timestamp': datetime.now().isoformat(),
            'node_id': self._node_id,
            'reason': reason
        }
        
        try:
            # Publish the invalidation event
            await self._redis.publish(self._channel, json.dumps(event))
            logger.debug(f"Published invalidation for pattern: {pattern}")
        except RedisError as e:
            logger.error(f"Failed to publish pattern invalidation: {e}")
            raise InvalidationError(f"Failed to publish pattern invalidation: {e}") from e
    
    async def invalidate_namespace(self, namespace: str, reason: Optional[str] = None) -> None:
        """Invalidate all cache keys in a namespace.
        
        Args:
            namespace: Cache namespace to invalidate
            reason: Optional reason for invalidation
            
        Raises:
            InvalidationError: If there's an error publishing the event
        """
        if not self.enabled or self._redis is None:
            return
            
        event = {
            'type': InvalidationEvent.NAMESPACE.value,
            'namespace': namespace,
            'timestamp': datetime.now().isoformat(),
            'node_id': self._node_id,
            'reason': reason
        }
        
        try:
            # Publish the invalidation event
            await self._redis.publish(self._channel, json.dumps(event))
            logger.debug(f"Published invalidation for namespace: {namespace}")
        except RedisError as e:
            logger.error(f"Failed to publish namespace invalidation: {e}")
            raise InvalidationError(f"Failed to publish namespace invalidation: {e}") from e
    
    def get_last_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent invalidation events.
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            List of recent invalidation events
        """
        return self._last_events[-limit:] if self._last_events else [] 
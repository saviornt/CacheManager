"""Telemetry and observability system for the CacheManager.

This module provides classes for collecting metrics, reporting telemetry data,
and hooking into various cache operations for observability.
"""

import time
import logging
import json
import asyncio
import os
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from collections import deque, defaultdict
from functools import wraps
import threading

logger = logging.getLogger(__name__)

class MetricType(str, Enum):
    """Types of metrics that can be collected."""
    COUNTER = "counter"  # Cumulative count (e.g., total hits)
    GAUGE = "gauge"      # Point-in-time value (e.g., current memory usage)
    TIMING = "timing"    # Duration measurement (e.g., operation latency)
    HISTOGRAM = "histogram"  # Distribution of values

class CacheEvent(str, Enum):
    """Cache operation events that can be observed."""
    GET = "get"
    SET = "set"
    DELETE = "delete"
    HIT = "hit"
    MISS = "miss"
    EVICTION = "eviction"
    ERROR = "error"
    WARNING = "warning"
    STARTUP = "startup"
    SHUTDOWN = "shutdown"
    CLEAR = "clear"

class TelemetryManager:
    """Manages telemetry collection for cache operations.
    
    Collects metrics on cache operations and can generate reports.
    """
    def __init__(
        self, 
        enabled: bool = False,
        report_interval: int = 60,
        log_dir: str = 'logs'
    ):
        """Initialize the telemetry manager.
        
        Args:
            enabled: Whether telemetry collection is enabled
            report_interval: How often to generate reports (in seconds)
            log_dir: Directory to store telemetry logs
        """
        self.enabled = enabled
        self.report_interval = report_interval
        self.log_dir = log_dir
        
        # Initialize metrics
        self._timers = defaultdict(list)
        self._counters = defaultdict(int)
        self._gauges = {}
        self._histograms = {}
        
        # Ensure necessary counters are initialized
        self._counters['cache.hit'] = 0
        self._counters['cache.miss'] = 0
        self._counters['cache.set'] = 0
        self._counters['cache.delete'] = 0
        self._counters['cache.error'] = 0

        # Setup lock for thread safety
        self._lock = threading.RLock()
        
        # Metric history for time-series data
        self._metric_history: Dict[str, deque] = {}
        
        # Event listeners/hooks
        self._event_listeners: Dict[CacheEvent, List[Callable]] = {
            event: [] for event in CacheEvent
        }
        
        # Periodic reporting task
        self._reporting_task = None
        
        # Ensure log directory exists
        if not os.path.exists(log_dir) and enabled:
            os.makedirs(log_dir, exist_ok=True)
            
        self._telemetry_file = os.path.join(
            log_dir, 
            f"telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
        )
    
    async def start(self) -> None:
        """Start the telemetry collection and reporting."""
        if not self.enabled:
            return
            
        logger.info("Starting telemetry collection")
        self._record_event(CacheEvent.STARTUP, {"timestamp": time.time()})
        
        # Start periodic reporting
        if self.report_interval > 0:
            self._reporting_task = asyncio.create_task(self._periodic_report())
    
    async def stop(self) -> None:
        """Stop the telemetry collection and reporting."""
        if not self.enabled or self._reporting_task is None:
            return
            
        logger.info("Stopping telemetry collection")
        self._record_event(CacheEvent.SHUTDOWN, {"timestamp": time.time()})
        
        # Cancel the reporting task
        if self._reporting_task:
            self._reporting_task.cancel()
            try:
                await self._reporting_task
            except asyncio.CancelledError:
                pass
            self._reporting_task = None
        
        # Generate final report
        await self._write_metrics_report()
    
    def add_event_listener(self, event: CacheEvent, callback: Callable) -> None:
        """Add a listener for a specific cache event.
        
        Args:
            event: The event type to listen for
            callback: Function to call when event occurs
        """
        if not self.enabled:
            return
            
        self._event_listeners[event].append(callback)
    
    def remove_event_listener(self, event: CacheEvent, callback: Callable) -> None:
        """Remove a listener for a specific cache event.
        
        Args:
            event: The event type
            callback: The callback function to remove
        """
        if not self.enabled:
            return
            
        if callback in self._event_listeners[event]:
            self._event_listeners[event].remove(callback)
    
    def _record_event(self, event: CacheEvent, data: Dict[str, Any]) -> None:
        """Record a cache event and execute any registered listeners.
        
        Args:
            event: The event that occurred
            data: Additional data about the event
        """
        if not self.enabled:
            return
            
        # Add timestamp if not present
        if "timestamp" not in data:
            data["timestamp"] = time.time()
            
        # Call all listeners for this event
        for listener in self._event_listeners[event]:
            try:
                listener(data)
            except Exception as e:
                logger.error(f"Error in event listener for {event}: {e}")
                
        # Log the event
        self._log_telemetry(event=str(event), data=data)
    
    def _log_telemetry(self, event: str, data: Dict[str, Any]) -> None:
        """Write telemetry data to log file.
        
        Args:
            event: The event name
            data: The event data
        """
        if not self.enabled:
            return
            
        try:
            log_entry = {
                "event": event,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            
            with open(self._telemetry_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to log telemetry: {e}")
    
    # Metric collection methods
    def increment(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric.
        
        Args:
            name: Metric name
            value: Amount to increment by
            tags: Optional tags for the metric
        """
        if not self.enabled:
            return
            
        full_name = self._get_metric_name(name, tags)
        if full_name not in self._counters:
            self._counters[full_name] = 0
        self._counters[full_name] += value
        
        # Add to history
        self._add_to_history(full_name, self._counters[full_name], MetricType.COUNTER)
    
    def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric value.
        
        Args:
            name: Metric name
            value: Current value
            tags: Optional tags for the metric
        """
        if not self.enabled:
            return
            
        full_name = self._get_metric_name(name, tags)
        self._gauges[full_name] = value
        
        # Add to history
        self._add_to_history(full_name, value, MetricType.GAUGE)
    
    def timing(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a timing metric.
        
        Args:
            name: Metric name
            value: Duration in milliseconds
            tags: Optional tags for the metric
        """
        if not self.enabled:
            return
            
        full_name = self._get_metric_name(name, tags)
        if full_name not in self._timers:
            self._timers[full_name] = []
        self._timers[full_name].append(value)
        
        # Limit the list size
        if len(self._timers[full_name]) > 1000:
            self._timers[full_name] = self._timers[full_name][-1000:]
        
        # Add to history
        self._add_to_history(full_name, value, MetricType.TIMING)
    
    def histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a value for histogram distribution.
        
        Args:
            name: Metric name
            value: Value to record
            tags: Optional tags for the metric
        """
        if not self.enabled:
            return
            
        full_name = self._get_metric_name(name, tags)
        if full_name not in self._histograms:
            self._histograms[full_name] = {}
        
        # Round the value for the bucket
        bucket = int(value)
        if bucket not in self._histograms[full_name]:
            self._histograms[full_name][bucket] = 0
        self._histograms[full_name][bucket] += 1
        
        # Add to history with the bucket
        self._add_to_history(full_name, (bucket, self._histograms[full_name][bucket]), 
                            MetricType.HISTOGRAM)
    
    def _get_metric_name(self, name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """Format a metric name with optional tags.
        
        Args:
            name: Base metric name
            tags: Tags to include in the name
            
        Returns:
            Formatted metric name with tags
        """
        if not tags:
            return name
            
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"
    
    def _add_to_history(self, name: str, value: Any, metric_type: MetricType) -> None:
        """Add a metric point to the historical time series.
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Type of metric
        """
        if name not in self._metric_history:
            self._metric_history[name] = deque(maxlen=self.max_history)
            
        self._metric_history[name].append({
            "timestamp": time.time(),
            "value": value,
            "type": metric_type
        })
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all recorded metrics.
        
        Returns:
            Dict[str, Any]: Dictionary of all metrics
        """
        if not self.enabled:
            return {
                "counters": {},
                "gauges": {},
                "timers": {},
                "histograms": {}
            }
            
        with self._lock:
            return {
                "counters": self._counters.copy(),
                "gauges": self._gauges.copy(),
                "timers": {
                    k: {
                        "count": len(v),
                        "min": min(v) if v else 0,
                        "max": max(v) if v else 0,
                        "avg": sum(v) / len(v) if v else 0,
                        "p95": sorted(v)[int(len(v) * 0.95)] if len(v) > 10 else None
                    } for k, v in self._timers.items()
                },
                "histograms": self._histograms.copy(),
            }
    
    async def _periodic_report(self) -> None:
        """Run periodic metrics reporting task."""
        while True:
            try:
                await asyncio.sleep(self.report_interval)
                await self._write_metrics_report()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in telemetry reporting: {e}")
    
    async def _write_metrics_report(self) -> None:
        """Write a metrics report to the log directory."""
        if not self.enabled:
            return
            
        try:
            metrics = self.get_metrics()
            self._log_telemetry(event="metrics_report", data=metrics)
        except Exception as e:
            logger.error(f"Failed to write metrics report: {e}")

    def record_timer(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a timing metric.
        
        Args:
            name: Name of the metric
            value: Time value in seconds
            tags: Optional tags to add
        """
        if not self.enabled:
            return
            
        with self._lock:
            full_name = self._get_metric_name(name, tags)
            self._timers[full_name].append(value)
            
            # Limit the list size
            if len(self._timers[full_name]) > 1000:
                self._timers[full_name] = self._timers[full_name][-1000:]

    def record_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record a gauge metric.
        
        Args:
            name: Name of the metric
            value: Gauge value
            tags: Optional tags to add
        """
        if not self.enabled:
            return
            
        with self._lock:
            full_name = self._get_metric_name(name, tags)
            self._gauges[full_name] = value


# Decorator for timing cache operations
def timed_operation(operation_name: str, tags: Optional[Dict[str, str]] = None) -> Callable:
    """Decorator to time operations and record metrics.
    
    Args:
        operation_name: Name of the operation being timed
        tags: Optional tags to add to the metric
    
    Returns:
        Callable: Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Skip timing if telemetry is disabled
            if not hasattr(self, '_telemetry') or not self._telemetry or not self._telemetry.enabled:
                return await func(self, *args, **kwargs)
                
            start_time = time.time()
            try:
                result = await func(self, *args, **kwargs)
                
                # Record operation time
                elapsed = time.time() - start_time
                self._telemetry.record_timer(f"cache.{operation_name}.time", elapsed, tags)
                
                # Record operation counter
                self._telemetry._counters[f"cache.{operation_name}"] += 1
                
                # For get operations, record hit or miss
                if operation_name == 'get' and args:
                    if result is not None:
                        self._telemetry._counters['cache.hit'] += 1
                    else:
                        self._telemetry._counters['cache.miss'] += 1
                
                return result
            except Exception as e:
                # Record error
                logger.error(f"Error in timed operation {operation_name}: {e}")
                self._telemetry._counters['cache.error'] += 1
                raise
                
        return wrapper
    return decorator 
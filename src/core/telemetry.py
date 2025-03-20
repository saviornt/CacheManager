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
from typing import Dict, List, Optional, Any, Callable, Set, Union, Tuple
from collections import deque
from functools import wraps

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
    """Manages telemetry data collection and reporting.
    
    Collects metrics on cache operations, performance data, and provides
    hooks for observability into the cache system.
    """
    
    def __init__(
        self, 
        enabled: bool = False,
        report_interval: int = 60,
        max_metrics_history: int = 1000,
        log_dir: str = "./logs"
    ):
        """Initialize the telemetry manager.
        
        Args:
            enabled: Whether telemetry collection is enabled
            report_interval: How often to report metrics (in seconds)
            max_metrics_history: Max number of metric points to keep in history
            log_dir: Directory for telemetry log files
        """
        self.enabled = enabled
        self.report_interval = report_interval
        self.max_history = max_metrics_history
        self.log_dir = log_dir
        
        # Metric storage
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._timings: Dict[str, List[float]] = {}
        self._histograms: Dict[str, Dict[int, int]] = {}
        
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
        if full_name not in self._timings:
            self._timings[full_name] = []
        self._timings[full_name].append(value)
        
        # Limit the list size
        if len(self._timings[full_name]) > 1000:
            self._timings[full_name] = self._timings[full_name][-1000:]
        
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
        """Get current metrics snapshot.
        
        Returns:
            Dict containing all current metric values
        """
        if not self.enabled:
            return {}
            
        metrics = {
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
            "timings": {
                k: {
                    "count": len(v),
                    "min": min(v) if v else 0,
                    "max": max(v) if v else 0,
                    "avg": sum(v) / len(v) if v else 0,
                    "p95": sorted(v)[int(len(v) * 0.95)] if len(v) > 10 else None
                } for k, v in self._timings.items()
            },
            "histograms": self._histograms.copy(),
            "timestamp": time.time()
        }
        return metrics
    
    async def _periodic_report(self) -> None:
        """Periodically write metrics report."""
        while True:
            try:
                await asyncio.sleep(self.report_interval)
                await self._write_metrics_report()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in telemetry reporting: {e}")
    
    async def _write_metrics_report(self) -> None:
        """Write current metrics to the telemetry log."""
        if not self.enabled:
            return
            
        try:
            metrics = self.get_metrics()
            self._log_telemetry(event="metrics_report", data=metrics)
        except Exception as e:
            logger.error(f"Failed to write metrics report: {e}")


# Decorator for timing cache operations
def timed_operation(event_name: str):
    """Decorator to time a cache operation and record metrics.
    
    Args:
        event_name: The name of the operation to time
        
    Returns:
        Decorator function that times the operation
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Skip if telemetry is disabled or not initialized
            if not hasattr(self, '_telemetry') or not self._telemetry.enabled:
                return await func(self, *args, **kwargs)
            
            # Start timing
            start_time = time.time()
            
            try:
                # Execute the function
                result = await func(self, *args, **kwargs)
                
                # Record successful operation timing
                duration_ms = (time.time() - start_time) * 1000
                self._telemetry.timing(
                    f"cache.{event_name}.duration", 
                    duration_ms,
                    {"success": "true"}
                )
                
                return result
            except Exception as e:
                # Record failed operation timing
                duration_ms = (time.time() - start_time) * 1000
                self._telemetry.timing(
                    f"cache.{event_name}.duration", 
                    duration_ms,
                    {"success": "false", "error": str(type(e).__name__)}
                )
                
                # Record error event
                self._telemetry._record_event(
                    CacheEvent.ERROR,
                    {
                        "operation": event_name,
                        "error": str(e),
                        "error_type": str(type(e).__name__)
                    }
                )
                
                # Re-raise the exception
                raise
                
        return wrapper
    return decorator 
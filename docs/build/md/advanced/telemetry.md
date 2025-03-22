# Telemetry

CacheManager includes comprehensive telemetry capabilities for monitoring cache performance, usage patterns, and health metrics.

## Overview

The telemetry system provides insights into:

- Cache hit/miss rates
- Operation latencies
- Memory usage and evictions
- Layer-specific performance metrics

## Configuration

To enable telemetry:

```python
from src.cache_manager import CacheManager
from src.cache_config import CacheConfig

config = CacheConfig(
    enable_telemetry=True,
    telemetry_interval=60,  # Collect metrics every 60 seconds
    metrics_collection=True
)

cache = CacheManager(config=config)
```

## Available Metrics

CacheManager collects the following metrics:

- **Hit Rate**: Percentage of successful cache lookups
- **Miss Rate**: Percentage of failed cache lookups
- **Latency**: Timing for get/set/delete operations
- **Size**: Current cache size and item count
- **Evictions**: Number of items evicted by policy
- **Errors**: Count of various error types
- **TTL**: Time-to-live statistics

## Accessing Metrics

Metrics can be accessed programmatically:

```python
# Get current metrics
metrics = cache.get_stats()

# Print hit rate
print(f"Hit rate: {metrics['hit_rate']:.2f}%")

# Get metrics for a specific period
hourly_metrics = cache.get_stats(period="hour")
daily_metrics = cache.get_stats(period="day")
```

## Exporting Metrics

Metrics can be exported to various monitoring systems:

```python
config = CacheConfig(
    enable_telemetry=True,
    telemetry_export=True,
    telemetry_export_format="prometheus",  # or "statsd", "json"
    telemetry_export_endpoint="localhost:9090"
)
```

## Alerting

Set up alerting based on cache metrics:

```python
# Configure alert thresholds
config = CacheConfig(
    enable_telemetry=True,
    alert_on_high_miss_rate=True,
    high_miss_rate_threshold=0.50,  # Alert when miss rate exceeds 50%
    alert_on_high_latency=True,
    high_latency_threshold=100  # Alert when latency exceeds 100ms
)

# Register alert handler
def alert_handler(alert_type, details):
    print(f"ALERT: {alert_type} - {details}")

cache = CacheManager(config=config)
cache.register_alert_handler(alert_handler)
```

## Visualization

The telemetry system can generate visualizations for easy monitoring:

```python
# Generate HTML dashboard
dashboard_html = cache.generate_dashboard()

# Save to file
with open("cache_dashboard.html", "w") as f:
    f.write(dashboard_html)
```

For more advanced metrics and integration with monitoring systems, see the API reference.

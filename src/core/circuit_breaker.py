"""Circuit breaker pattern implementation to prevent operation cascading failures."""

import functools
import uuid
import logging
from datetime import datetime
from threading import RLock
from typing import Any, Callable, TypeVar

T = TypeVar('T')

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Circuit breaker pattern implementation to prevent operation cascading failures.
    
    When errors exceed the threshold, the circuit opens and operations return a default value.
    After a timeout period, the circuit closes and operations are attempted again.
    """
    def __init__(self, 
                 failure_threshold: int = 5, 
                 reset_timeout: int = 60,
                 operation_name: str = "unnamed"):
        """Initialize a circuit breaker.
        
        Args:
            failure_threshold: Number of consecutive failures before opening the circuit
            reset_timeout: Seconds to wait before trying to reset (close) the circuit
            operation_name: Name of the operation using this circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.operation_name = operation_name
        
        # Initial state
        self.failures = 0
        self.is_open = False
        self.last_failure_time = None
        self._lock = RLock()
        
        self._correlation_id = f"CB-{uuid.uuid4().hex[:8]}"
        
    def record_success(self) -> None:
        """Record a successful operation, resetting the failure count."""
        with self._lock:
            self.failures = 0
            self.is_open = False
    
    def record_failure(self) -> None:
        """Record a failed operation, possibly opening the circuit."""
        with self._lock:
            self.failures += 1
            self.last_failure_time = datetime.now()
            
            if self.failures >= self.failure_threshold:
                if not self.is_open:
                    logger.warning(
                        f"Circuit breaker for '{self.operation_name}' opened after "
                        f"{self.failures} consecutive failures",
                        extra={'correlation_id': self._correlation_id}
                    )
                self.is_open = True
    
    def allow_request(self) -> bool:
        """Check if the request should be allowed through the circuit.
        
        Returns:
            bool: True if the request should be allowed, False otherwise
        """
        with self._lock:
            # If circuit is closed, allow the request
            if not self.is_open:
                return True
                
            # If circuit is open, check if reset timeout has elapsed
            if self.last_failure_time is None:
                return True
                
            # Try to reset after the timeout
            elapsed = datetime.now() - self.last_failure_time
            if elapsed.total_seconds() >= self.reset_timeout:
                logger.info(
                    f"Circuit breaker for '{self.operation_name}' reset after "
                    f"{elapsed.total_seconds():.1f} seconds",
                    extra={'correlation_id': self._correlation_id}
                )
                self.is_open = False  # Try again (half-open state)
                return True
                
            return False
            
    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to wrap a function with circuit breaker functionality.
        
        Args:
            func: The async function to wrap
            
        Returns:
            Callable: Wrapped function
        """
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not self.allow_request():
                logger.warning(
                    f"Circuit is open for '{self.operation_name}', operation skipped",
                    extra={'correlation_id': self._correlation_id}
                )
                return None
                
            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                logger.error(
                    f"Circuit breaker caught error in '{self.operation_name}': {e}",
                    extra={'correlation_id': self._correlation_id}
                )
                raise
                
        return wrapper 
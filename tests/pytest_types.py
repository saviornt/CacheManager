"""Type definitions for pytest fixtures.

This module provides type annotations for pytest fixtures to ensure
consistent typing throughout the test suite.
"""

from typing import TypeVar, Protocol, Optional, runtime_checkable

# The correct way to define fixture types for pytest
T_co = TypeVar('T_co', covariant=True)
S_contra = TypeVar('S_contra', contravariant=True)

# Define our own FixtureFunction type that matches pytest's internal type
@runtime_checkable
class SimpleFixtureFunction(Protocol[T_co]):
    """Protocol for a simple fixture function that returns a value."""
    def __call__(self) -> T_co: ...

@runtime_checkable
class FactoryFixtureFunction(Protocol[T_co, S_contra]):
    """Protocol for a fixture function that takes a parameter and returns a value."""
    def __call__(self, request: S_contra) -> T_co: ...

@runtime_checkable
class FixtureFunction(Protocol[T_co, S_contra]):
    """Protocol for a fixture function that matches pytest's internal type.
    
    This type requires two type parameters:
    - T_co: The return type of the fixture (covariant)
    - S_contra: The type of the request parameter (contravariant)
    
    Example usage:
        def my_fixture() -> FixtureFunction[Dict[str, Any], None]:
            def _fixture(request: Optional[None] = None) -> Dict[str, Any]:
                return {"test": "data"}
            return _fixture
    """
    def __call__(self, request: Optional[S_contra] = None) -> T_co: ... 
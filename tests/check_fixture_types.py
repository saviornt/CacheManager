"""Check fixture typing to identify the issue with FixtureFunction."""

import pytest
from typing import Any, Generator, Dict, Optional

from tests.pytest_types import FixtureFunction

# Correct usage of fixture types
@pytest.fixture
def correct_fixture() -> Generator[Dict[str, Any], None, None]:
    """Example fixture with correct typing."""
    yield {"test": "data"}

# Example of a properly typed fixture function
def my_fixture_function() -> FixtureFunction[Dict[str, Any], Any]:
    """Example of a properly typed fixture function with both type parameters."""
    def _fixture(request: Optional[Any] = None) -> Dict[str, Any]:
        return {"test": "data"}
    return _fixture

# Simple test to verify
def test_fixture_typing(correct_fixture: Dict[str, Any]) -> None:
    """Test to verify fixture works."""
    assert correct_fixture["test"] == "data" 
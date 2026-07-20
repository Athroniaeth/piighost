"""Tests for the exception hierarchy.

The expected tree is declared once in EXCEPTION_HIERARCHY and verified by a
parametrized test, so it stays explicit and adding an exception is a single
line. Importing the classes here also guards their names: a removed or renamed
exception breaks this module.
"""

import pytest

from piighost.exceptions import (
    ConfidenceError,
    DetectionError,
    EmptyEntityError,
    EmptyPepperError,
    EntityError,
    HasherError,
    MixedLabelError,
    NegativeSpanStartError,
    PIIGhostError,
    SpanError,
    SpanOrderingError,
)

# Each error mapped to its expected direct parent. The chain
# NegativeSpanStartError -> SpanError -> PIIGhostError -> Exception means
# except PIIGhostError catches every library error.
EXCEPTION_HIERARCHY: dict[type[Exception], type[Exception]] = {
    PIIGhostError: Exception,
    SpanError: PIIGhostError,
    NegativeSpanStartError: SpanError,
    SpanOrderingError: SpanError,
    DetectionError: PIIGhostError,
    ConfidenceError: DetectionError,
    EntityError: PIIGhostError,
    EmptyEntityError: EntityError,
    MixedLabelError: EntityError,
    HasherError: PIIGhostError,
    EmptyPepperError: HasherError,
}


@pytest.mark.parametrize(("error", "parent"), EXCEPTION_HIERARCHY.items())
def test_error_has_expected_direct_parent(
    error: type[Exception], parent: type[Exception]
) -> None:
    """Check that no exception's parent changed, which would break catches."""
    assert error.__bases__ == (parent,)

"""Tests for the detector exception family."""

import pytest

from piighost.exceptions import DetectorError, LabelMappingError, PIIGhostError

EXCEPTION_HIERARCHY: dict[type[Exception], type[Exception]] = {
    DetectorError: PIIGhostError,
    LabelMappingError: DetectorError,
}
"""Each detector error mapped to an ancestor it must subclass."""


@pytest.mark.parametrize(("error", "ancestor"), EXCEPTION_HIERARCHY.items())
def test_error_subclasses_its_ancestor(
    error: type[Exception], ancestor: type[Exception]
) -> None:
    """Each detector error is catchable as its declared ancestor."""
    assert issubclass(error, ancestor)

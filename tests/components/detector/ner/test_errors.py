"""Tests for the detector exception family."""

from piighost.exceptions import DetectorError, LabelMappingError, PIIGhostError


def test_detector_error_is_a_piighost_error() -> None:
    """DetectorError sits under the shared PIIGhostError root."""
    assert issubclass(DetectorError, PIIGhostError)


def test_label_mapping_error_is_a_detector_error() -> None:
    """LabelMappingError is a DetectorError, catchable as either."""
    assert issubclass(LabelMappingError, DetectorError)

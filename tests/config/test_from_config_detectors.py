import pytest

from piighost.config.models.detector import RegexDetectorConfig
from piighost.detector.base import RegexDetector


@pytest.mark.asyncio
async def test_regex_detector_from_config_produces_working_instance():
    cfg = RegexDetectorConfig(
        type="regex",
        name="common",
        patterns={"EMAIL": r"[a-z]+@[a-z]+\.[a-z]+"},
    )
    detector = RegexDetector.from_config(cfg)
    assert isinstance(detector, RegexDetector)

    detections = await detector.detect("contact: alice@example.com")
    assert len(detections) == 1
    assert detections[0].label == "EMAIL"
    assert detections[0].text == "alice@example.com"


def test_regex_detector_config_classvar_points_to_config_model():
    assert RegexDetector.Config is RegexDetectorConfig

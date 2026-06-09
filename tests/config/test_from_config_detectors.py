import pytest

from piighost.config.builders import _DETECTOR_BUILDERS, build_detector
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


def test_build_detector_dispatches_regex():
    cfg = RegexDetectorConfig(type="regex", patterns={"EMAIL": r"\S+@\S+"})
    detector = build_detector(cfg)
    assert isinstance(detector, RegexDetector)


def test_every_detector_config_has_a_builder():
    from piighost.config.models.detector import (
        ChunkedDetectorConfig,
        Gliner2DetectorConfig,
        LLMDetectorConfig,
        RegexDetectorConfig,
        SpacyDetectorConfig,
        TransformersDetectorConfig,
    )

    expected = {
        RegexDetectorConfig,
        ChunkedDetectorConfig,
        Gliner2DetectorConfig,
        SpacyDetectorConfig,
        TransformersDetectorConfig,
        LLMDetectorConfig,
    }
    assert expected.issubset(set(_DETECTOR_BUILDERS.keys()))


def test_every_lazy_builder_key_is_resolvable():
    """Each lazy string in the dispatch dict must be known to the resolver.

    ImportError means the optional extra is not installed (acceptable);
    KeyError would mean a typo in the dispatch dict (a real bug).
    """
    from piighost.config.builders import _resolve_lazy_detector

    for builder in _DETECTOR_BUILDERS.values():
        if isinstance(builder, str):
            try:
                _resolve_lazy_detector(builder)
            except ImportError:
                pass


@pytest.mark.asyncio
async def test_chunked_detector_from_config_wraps_inner_regex():
    from piighost.config.models.detector import (
        ChunkedDetectorConfig,
        RegexDetectorConfig,
    )
    from piighost.detector.chunked import ChunkedDetector

    cfg = ChunkedDetectorConfig(
        type="chunked",
        chunk_size=1000,
        inner=RegexDetectorConfig(
            type="regex", patterns={"EMAIL": r"[a-z]+@[a-z]+\.[a-z]+"}
        ),
    )
    detector = ChunkedDetector.from_config(cfg)
    detections = await detector.detect("contact: alice@example.com")
    assert len(detections) == 1
    assert detections[0].label == "EMAIL"

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


def test_gliner2_detector_dispatch_mapping():
    from piighost.config.models.detector import Gliner2DetectorConfig

    assert _DETECTOR_BUILDERS[Gliner2DetectorConfig] == "lazy:gliner2"


def test_spacy_detector_dispatch_mapping():
    from piighost.config.models.detector import SpacyDetectorConfig

    assert _DETECTOR_BUILDERS[SpacyDetectorConfig] == "lazy:spacy"


def test_transformers_detector_dispatch_mapping():
    from piighost.config.models.detector import TransformersDetectorConfig

    assert _DETECTOR_BUILDERS[TransformersDetectorConfig] == "lazy:transformers"


def test_llm_detector_dispatch_mapping():
    from piighost.config.models.detector import LLMDetectorConfig

    assert _DETECTOR_BUILDERS[LLMDetectorConfig] == "lazy:llm"


def test_chunked_detector_dispatch_mapping():
    from piighost.config.models.detector import ChunkedDetectorConfig

    assert _DETECTOR_BUILDERS[ChunkedDetectorConfig] == "lazy:chunked"


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

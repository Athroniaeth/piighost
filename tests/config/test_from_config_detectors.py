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


@pytest.mark.integration
def test_gliner2_detector_config_classvar():
    from piighost.config.models.detector import Gliner2DetectorConfig
    from piighost.detector.gliner2 import Gliner2Detector

    assert Gliner2Detector.Config is Gliner2DetectorConfig


@pytest.mark.integration
def test_spacy_detector_config_classvar():
    from piighost.config.models.detector import SpacyDetectorConfig
    from piighost.detector.spacy import SpacyDetector

    assert SpacyDetector.Config is SpacyDetectorConfig


@pytest.mark.integration
def test_transformers_detector_config_classvar():
    from piighost.config.models.detector import TransformersDetectorConfig
    from piighost.detector.transformers import TransformersDetector

    assert TransformersDetector.Config is TransformersDetectorConfig


@pytest.mark.integration
def test_llm_detector_config_classvar():
    from piighost.config.models.detector import LLMDetectorConfig
    from piighost.detector.llm import LLMDetector

    assert LLMDetector.Config is LLMDetectorConfig


def test_chunked_detector_config_classvar():
    from piighost.config.models.detector import ChunkedDetectorConfig
    from piighost.detector.chunked import ChunkedDetector

    assert ChunkedDetector.Config is ChunkedDetectorConfig


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

import pytest
from pydantic import ValidationError, TypeAdapter

from piighost.config.models.common import _ComponentConfig
from piighost.config.models.detector import (
    ChunkedDetectorConfig,
    DetectorConfig,
    Gliner2DetectorConfig,
    LLMDetectorConfig,
    RegexDetectorConfig,
    SpacyDetectorConfig,
    TransformersDetectorConfig,
)


class _Sample(_ComponentConfig):
    x: int


def test_component_config_forbids_extra_keys():
    with pytest.raises(ValidationError) as exc:
        _Sample.model_validate({"x": 1, "rogue": True})
    assert "rogue" in str(exc.value)


def test_component_config_is_frozen():
    s = _Sample.model_validate({"x": 1})
    with pytest.raises(ValidationError):
        s.x = 2


_DETECTOR_ADAPTER = TypeAdapter(DetectorConfig)


def test_regex_detector_parses():
    cfg = _DETECTOR_ADAPTER.validate_python(
        {"type": "regex", "name": "common", "patterns": {"EMAIL": r"\S+@\S+"}}
    )
    assert isinstance(cfg, RegexDetectorConfig)
    assert cfg.name == "common"
    assert cfg.patterns == {"EMAIL": r"\S+@\S+"}


def test_gliner2_detector_parses_with_threshold_bounds():
    cfg = _DETECTOR_ADAPTER.validate_python(
        {
            "type": "gliner2",
            "model": "fastino/gliner2-multi-v1",
            "threshold": 0.5,
            "labels": ["person"],
        }
    )
    assert isinstance(cfg, Gliner2DetectorConfig)


def test_gliner2_rejects_threshold_above_one():
    with pytest.raises(ValidationError):
        _DETECTOR_ADAPTER.validate_python(
            {
                "type": "gliner2",
                "model": "x",
                "threshold": 1.5,
                "labels": ["person"],
            }
        )


def test_gliner2_rejects_empty_labels():
    with pytest.raises(ValidationError):
        _DETECTOR_ADAPTER.validate_python(
            {"type": "gliner2", "model": "x", "labels": []}
        )


def test_unknown_detector_type_is_rejected():
    with pytest.raises(ValidationError) as exc:
        _DETECTOR_ADAPTER.validate_python({"type": "http", "endpoint": "x"})
    # Discriminator error names the bad tag.
    assert "http" in str(exc.value)


def test_chunked_detector_nests_inner():
    cfg = _DETECTOR_ADAPTER.validate_python(
        {
            "type": "chunked",
            "chunk_size": 1000,
            "inner": {
                "type": "regex",
                "patterns": {"EMAIL": r"\S+@\S+"},
            },
        }
    )
    assert isinstance(cfg, ChunkedDetectorConfig)
    assert isinstance(cfg.inner, RegexDetectorConfig)

from pathlib import Path

import pytest

from piighost.config.errors import ConfigError
from piighost.config.loader import build_pipeline, load_config, load_pipeline
from piighost.config.models.pipeline import PipelineConfig
from piighost.detector.base import CompositeDetector, RegexDetector
from piighost.pipeline.thread import ThreadAnonymizationPipeline

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_config_returns_pipeline_config():
    cfg = load_config(FIXTURES / "minimal.toml")
    assert isinstance(cfg, PipelineConfig)
    assert len(cfg.detectors) == 1


def test_load_config_raises_config_error_on_missing_file():
    with pytest.raises(ConfigError):
        load_config(FIXTURES / "does_not_exist.toml")


def test_build_pipeline_returns_pipeline_and_manifest():
    cfg = load_config(FIXTURES / "minimal.toml")
    pipeline, manifest = build_pipeline(cfg)
    assert isinstance(pipeline, ThreadAnonymizationPipeline)
    assert manifest.name is None
    assert manifest.schema_version == 1
    assert len(manifest.detectors) == 1
    assert manifest.detectors[0].type == "regex"
    assert manifest.detectors[0].labels == ["EMAIL"]


def test_build_pipeline_creates_composite_for_multiple_detectors():
    cfg = load_config(FIXTURES / "multi_detector.toml")
    pipeline, manifest = build_pipeline(cfg)
    assert isinstance(pipeline._detector, CompositeDetector)
    assert len(pipeline._detector.detectors) == 2
    assert manifest.name == "demo"
    assert [d.name for d in manifest.detectors] == ["common", "secondary"]


def test_build_pipeline_single_detector_is_unwrapped():
    cfg = load_config(FIXTURES / "minimal.toml")
    pipeline, _ = build_pipeline(cfg)
    assert isinstance(pipeline._detector, RegexDetector)


def test_load_pipeline_combines_load_and_build():
    pipeline, manifest = load_pipeline(FIXTURES / "minimal.toml")
    assert isinstance(pipeline, ThreadAnonymizationPipeline)
    assert manifest.schema_version == 1

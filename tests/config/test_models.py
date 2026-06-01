import pytest
from pydantic import ValidationError, TypeAdapter

from piighost.config.models.common import _ComponentConfig
from piighost.config.models.detector import (
    ChunkedDetectorConfig,
    DetectorConfig,
    Gliner2DetectorConfig,
    RegexDetectorConfig,
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


from piighost.config.models.span_resolver import (
    ConfidenceSpanResolverConfig,
    DisabledSpanResolverConfig,
    SpanResolverConfig,
)
from piighost.config.models.entity_linker import (
    EntityLinkerConfig,
    ExactEntityLinkerConfig,
)
from piighost.config.models.entity_resolver import (
    EntityResolverConfig,
    FuzzyEntityResolverConfig,
    MergeEntityResolverConfig,
)


_SPAN_ADAPTER = TypeAdapter(SpanResolverConfig)
_LINKER_ADAPTER = TypeAdapter(EntityLinkerConfig)
_ENTITY_ADAPTER = TypeAdapter(EntityResolverConfig)


def test_span_resolver_confidence():
    cfg = _SPAN_ADAPTER.validate_python({"type": "confidence"})
    assert isinstance(cfg, ConfidenceSpanResolverConfig)


def test_span_resolver_disabled():
    cfg = _SPAN_ADAPTER.validate_python({"type": "disabled"})
    assert isinstance(cfg, DisabledSpanResolverConfig)


def test_entity_linker_exact():
    cfg = _LINKER_ADAPTER.validate_python({"type": "exact"})
    assert isinstance(cfg, ExactEntityLinkerConfig)


def test_entity_resolver_fuzzy_threshold_bounds():
    cfg = _ENTITY_ADAPTER.validate_python({"type": "fuzzy", "threshold": 0.85})
    assert isinstance(cfg, FuzzyEntityResolverConfig)
    assert cfg.threshold == 0.85
    with pytest.raises(ValidationError):
        _ENTITY_ADAPTER.validate_python({"type": "fuzzy", "threshold": 1.5})


def test_entity_resolver_merge_default():
    cfg = _ENTITY_ADAPTER.validate_python({"type": "merge"})
    assert isinstance(cfg, MergeEntityResolverConfig)


from piighost.config.models.anonymizer import (
    DefaultAnonymizerConfig,
)
from piighost.config.models.placeholder import (
    FakerCounterPlaceholderConfig,
    LabelCounterPlaceholderConfig,
    MaskPlaceholderConfig,
    PlaceholderFactoryConfig,
)


_PLACEHOLDER_ADAPTER = TypeAdapter(PlaceholderFactoryConfig)


def test_label_counter_placeholder_default():
    cfg = _PLACEHOLDER_ADAPTER.validate_python({"type": "label_counter"})
    assert isinstance(cfg, LabelCounterPlaceholderConfig)


def test_mask_placeholder_with_char():
    cfg = _PLACEHOLDER_ADAPTER.validate_python({"type": "mask", "mask_char": "*"})
    assert isinstance(cfg, MaskPlaceholderConfig)
    assert cfg.mask_char == "*"


def test_faker_counter_placeholder_locale():
    cfg = _PLACEHOLDER_ADAPTER.validate_python(
        {"type": "faker_counter", "locale": "fr_FR"}
    )
    assert isinstance(cfg, FakerCounterPlaceholderConfig)
    assert cfg.locale == "fr_FR"


def test_anonymizer_default_includes_placeholder_factory():
    cfg = DefaultAnonymizerConfig.model_validate(
        {
            "type": "default",
            "placeholder_factory": {"type": "label_counter"},
        }
    )
    assert isinstance(cfg.placeholder_factory, LabelCounterPlaceholderConfig)


def test_anonymizer_placeholder_defaults_to_label_counter():
    cfg = DefaultAnonymizerConfig.model_validate({"type": "default"})
    assert isinstance(cfg.placeholder_factory, LabelCounterPlaceholderConfig)


from piighost.config.models.pipeline import PipelineConfig, PipelineMeta


def test_pipeline_config_requires_at_least_one_detector():
    with pytest.raises(ValidationError):
        PipelineConfig.model_validate({"detectors": []})


def test_pipeline_config_applies_defaults():
    cfg = PipelineConfig.model_validate(
        {
            "detectors": [
                {"type": "regex", "patterns": {"EMAIL": r"\S+@\S+"}},
            ],
        }
    )
    assert isinstance(cfg.span_resolver, ConfidenceSpanResolverConfig)
    assert isinstance(cfg.entity_linker, ExactEntityLinkerConfig)
    assert isinstance(cfg.entity_resolver, MergeEntityResolverConfig)
    assert isinstance(cfg.anonymizer, DefaultAnonymizerConfig)
    assert isinstance(cfg.pipeline, PipelineMeta)
    assert cfg.pipeline.schema_version == 1


def test_pipeline_meta_optional_name():
    cfg = PipelineConfig.model_validate(
        {
            "pipeline": {"name": "demo"},
            "detectors": [
                {"type": "regex", "patterns": {"EMAIL": r"\S+@\S+"}},
            ],
        }
    )
    assert cfg.pipeline.name == "demo"


def test_gliner2_labels_accepts_dict():
    cfg = _DETECTOR_ADAPTER.validate_python(
        {"type": "gliner2", "model": "m", "labels": {"PERSONNE": "person"}}
    )
    assert cfg.labels == {"PERSONNE": "person"}


def test_gliner2_labels_still_accepts_list():
    cfg = _DETECTOR_ADAPTER.validate_python(
        {"type": "gliner2", "model": "m", "labels": ["person"]}
    )
    assert cfg.labels == ["person"]


def test_transformers_labels_optional_and_accepts_dict():
    bare = _DETECTOR_ADAPTER.validate_python({"type": "transformers", "model": "m"})
    assert bare.labels is None
    mapped = _DETECTOR_ADAPTER.validate_python(
        {"type": "transformers", "model": "m", "labels": {"PERSONNE": "PER"}}
    )
    assert mapped.labels == {"PERSONNE": "PER"}


def test_llm_labels_accepts_dict():
    cfg = _DETECTOR_ADAPTER.validate_python(
        {"type": "llm", "provider": "mistral", "model": "m", "labels": {"PERSONNE": "person"}}
    )
    assert cfg.labels == {"PERSONNE": "person"}

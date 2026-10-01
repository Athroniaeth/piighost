"""Tests for the model-backed detector config models (parse and dispatch only).

The gliner2, spacy, and transformers extras and an llm provider package are
absent from the dev environment, so these configs are exercised at the parse and
union-dispatch level; their build() is a deployment concern covered by the
components' own tests.
"""

import pytest
from pydantic import TypeAdapter

from piighost.config.models.detector import DetectorConfig
from piighost.config.models.detector_model import (
    Gliner2DetectorConfig,
    LLMDetectorConfig,
    PresidioDetectorConfig,
    SpacyDetectorConfig,
    TransformersDetectorConfig,
)


class TestModelDetectorParsing:
    def test_gliner2_parses_and_stores_fields(self) -> None:
        """The gliner2 config parses model, labels, and threshold."""
        config = Gliner2DetectorConfig(
            type="gliner2",
            model="urchade/gliner_small",
            labels=["PERSON"],
            threshold=0.7,
        )
        assert config.model == "urchade/gliner_small"
        assert config.labels == ["PERSON"]
        assert config.threshold == 0.7

    def test_gliner2_and_transformers_take_a_chunk_size(self) -> None:
        """max_chars is optional, unset by default, and parsed when given."""
        assert (
            Gliner2DetectorConfig(type="gliner2", model="m", labels=["A"]).max_chars
            is None
        )
        gliner2 = Gliner2DetectorConfig(
            type="gliner2", model="m", labels=["A"], max_chars=1000
        )
        transformers = TransformersDetectorConfig(
            type="transformers", model="m", max_chars=1000
        )
        assert gliner2.max_chars == transformers.max_chars == 1000

    def test_gliner2_build_forwards_the_chunk_size(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """build() hands max_chars to the detector, which chunks with it."""
        import sys
        import types

        captured: dict[str, object] = {}

        class _Detector:
            def __init__(self, **kwargs: object) -> None:
                captured.update(kwargs)

        module = types.ModuleType("piighost.components.detector.ner.gliner2")
        module.__dict__["Gliner2Detector"] = _Detector
        monkeypatch.setitem(sys.modules, module.__name__, module)
        Gliner2DetectorConfig(
            type="gliner2", model="m", labels=["A"], max_chars=1000
        ).build()
        assert captured["max_chars"] == 1000

    def test_a_chunk_size_must_be_positive(self) -> None:
        """A zero or negative max_chars is refused at parse time."""
        with pytest.raises(ValueError, match="max_chars"):
            Gliner2DetectorConfig.model_validate(
                {"type": "gliner2", "model": "m", "labels": ["A"], "max_chars": 0}
            )

    def test_spacy_parses_with_dict_labels(self) -> None:
        """The spacy config parses an emitted-to-model label mapping."""
        config = SpacyDetectorConfig(
            type="spacy", model="en_core_web_sm", labels={"PER": "PERSON"}
        )
        assert config.labels == {"PER": "PERSON"}

    def test_transformers_parses_threshold(self) -> None:
        """The transformers config parses the model and score threshold."""
        config = TransformersDetectorConfig(
            type="transformers", model="dslim/bert-base-NER", threshold=0.9
        )
        assert config.model == "dslim/bert-base-NER"
        assert config.threshold == 0.9

    def test_transformers_aggregation_strategy_defaults_to_simple(self) -> None:
        """The aggregation strategy defaults to simple and is overridable."""
        default = TransformersDetectorConfig(type="transformers", model="m")
        assert default.aggregation_strategy == "simple"
        custom = TransformersDetectorConfig(
            type="transformers", model="m", aggregation_strategy="max"
        )
        assert custom.aggregation_strategy == "max"

    def test_presidio_parses_language_and_threshold(self) -> None:
        """The presidio config parses labels, language, and threshold."""
        config = PresidioDetectorConfig(
            type="presidio",
            labels={"NAME": "PERSON"},
            language="fr",
            threshold=0.3,
        )
        assert config.labels == {"NAME": "PERSON"}
        assert config.language == "fr"
        assert config.threshold == 0.3

    def test_llm_parses_prompt_and_provider(self) -> None:
        """The llm config parses model, labels, prompt, and provider."""
        config = LLMDetectorConfig(
            type="llm",
            model="openai:gpt-4o-mini",
            labels=["PERSON"],
            provider="openai",
        )
        assert config.provider == "openai"


_DISPATCH_CASES = [
    ({"type": "gliner2", "model": "m", "labels": ["A"]}, Gliner2DetectorConfig),
    ({"type": "spacy", "model": "m"}, SpacyDetectorConfig),
    ({"type": "transformers", "model": "m"}, TransformersDetectorConfig),
    ({"type": "presidio"}, PresidioDetectorConfig),
    ({"type": "llm", "model": "m", "labels": ["A"]}, LLMDetectorConfig),
]
"""Each model detector payload paired with the config type it should dispatch to."""


@pytest.mark.parametrize(("data", "expected"), _DISPATCH_CASES)
def test_model_type_dispatches(data: dict[str, object], expected: type) -> None:
    """Each model detector type dispatches to its config through the union."""
    adapter = TypeAdapter(DetectorConfig)
    assert isinstance(adapter.validate_python(data), expected)

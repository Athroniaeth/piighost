"""Every operationally relevant constructor parameter must be reachable from TOML."""

import re

from piighost.config.loader import build_pipeline
from piighost.config.models.detector import RegexDetectorConfig
from piighost.config.models.entity_linker import ExactEntityLinkerConfig
from piighost.config.models.placeholder import (
    LabelHashPlaceholderConfig,
    MaskPlaceholderConfig,
    RedactCounterPlaceholderConfig,
    RedactHashPlaceholderConfig,
    RedactPlaceholderConfig,
)
from piighost.config.models.span_resolver import ConfidenceSpanResolverConfig
from piighost.detector.base import RegexDetector
from piighost.linker.entity import ExactEntityLinker
from piighost.placeholder import (
    LabelHashPlaceholderFactory,
    MaskPlaceholderFactory,
    RedactCounterPlaceholderFactory,
    RedactHashPlaceholderFactory,
    RedactPlaceholderFactory,
)
from piighost.resolver.span import ConfidenceSpanConflictResolver
from piighost.validators import validate_luhn


def test_confidence_threshold_flows_from_config():
    cfg = ConfidenceSpanResolverConfig(confidence_threshold=0.6)
    resolver = ConfidenceSpanConflictResolver.from_config(cfg)
    assert resolver._confidence_threshold == 0.6


def test_linker_options_flow_from_config():
    cfg = ExactEntityLinkerConfig(min_text_length=3, case_sensitive=True)
    linker = ExactEntityLinker.from_config(cfg)
    assert linker._min_text_length == 3
    assert linker._flags == re.RegexFlag(0)


def test_redact_value_and_prefixes_flow_from_config():
    assert (
        RedactPlaceholderFactory.from_config(
            RedactPlaceholderConfig(type="redact", value="HIDDEN")
        )._token
        == "<<HIDDEN>>"
    )
    assert (
        RedactCounterPlaceholderFactory.from_config(
            RedactCounterPlaceholderConfig(type="redact_counter", prefix="X")
        )._prefix
        == "X"
    )
    factory = RedactHashPlaceholderFactory.from_config(
        RedactHashPlaceholderConfig(type="redact_hash", prefix="X", salt="s1")
    )
    assert factory._prefix == "X" and factory._salt == "s1"


def test_label_hash_salt_flows_from_config():
    factory = LabelHashPlaceholderFactory.from_config(
        LabelHashPlaceholderConfig(type="label_hash", salt="s1", hash_length=12)
    )
    assert factory._salt == "s1" and factory._hash_length == 12


def test_mask_visible_chars_flow_from_config():
    factory = MaskPlaceholderFactory.from_config(
        MaskPlaceholderConfig(type="mask", mask_char="#", visible_chars=2)
    )
    # The numeric default strategy must honour visible_chars.
    assert factory._strategies["phone"]("0612345678", "#") == "########78"


def test_regex_validators_flow_from_config():
    cfg = RegexDetectorConfig(
        type="regex",
        patterns={"CREDIT_CARD": r"\b\d{13,19}\b"},
        validators={"CREDIT_CARD": "luhn"},
    )
    detector = RegexDetector.from_config(cfg)
    assert detector.validators["CREDIT_CARD"] is validate_luhn


def test_validator_registry_matches_config_literal():
    from typing import get_args, get_type_hints

    from piighost.config.models.detector import RegexDetectorConfig
    from piighost.detector.base import _VALIDATOR_REGISTRY

    hints = get_type_hints(RegexDetectorConfig)
    literal = hints["validators"].__args__[1]  # dict[str, Literal[...]] value type
    assert set(get_args(literal)) == set(_VALIDATOR_REGISTRY)


def _pipeline_from_toml(toml_text: str):
    try:
        import tomllib  # Python >= 3.11
    except ModuleNotFoundError:  # Python 3.10 falls back to the tomli backport
        import tomli as tomllib

    from piighost.config.models.pipeline import PipelineConfig

    cfg = PipelineConfig.model_validate(tomllib.loads(toml_text))
    pipeline, _ = build_pipeline(cfg)
    return pipeline


_MINIMAL_DETECTOR = """
[[detectors]]
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z]+\\\\.[a-z]+" }
"""


def test_cache_ttl_zero_disables_expiry():
    pipeline = _pipeline_from_toml("[pipeline]\ncache_ttl = 0\n" + _MINIMAL_DETECTOR)
    assert pipeline._cache_ttl is None


def test_cache_ttl_flows_from_config():
    pipeline = _pipeline_from_toml("[pipeline]\ncache_ttl = 120\n" + _MINIMAL_DETECTOR)
    assert pipeline._cache_ttl == 120


def test_cache_ttl_defaults_to_one_hour():
    pipeline = _pipeline_from_toml(_MINIMAL_DETECTOR)
    assert pipeline._cache_ttl == 3600


def test_mask_user_strategies_merge_on_top_of_defaults():
    factory = MaskPlaceholderFactory(strategies={"CUSTOM": lambda t, mc: "X"})
    # The custom label works AND the email default is still present.
    assert "email" in factory._strategies
    assert factory._strategies["custom"]("anything", "*") == "X"

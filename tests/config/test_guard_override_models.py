"""Tests for the guard and override config models."""

import pytest
from pydantic import TypeAdapter, ValidationError

from piighost.components.detector import RegexDetector
from piighost.components.guard import (
    DetectorGuardRail,
    ModerationGuardRail,
)
from piighost.components.override import (
    BlacklistStrategy,
    DetectionOverride,
    OverrideConflictStrategy,
    WhitelistStrategy,
)
from piighost.config.models.guard import (
    DetectorGuardRailConfig,
    GuardConfig,
    LLMGuardRailConfig,
    ModerationGuardRailConfig,
)
from piighost.config.models.override import OverrideConfig
from piighost.exceptions import ConfigError

_REGEX = {"type": "regex", "patterns": {"EMAIL": "[a-z]+@[a-z.]+"}}


class TestGuardConfig:
    def test_detector_guard_builds_over_its_detector(self) -> None:
        """The detector guard config builds a DetectorGuardRail on its detector."""
        config = DetectorGuardRailConfig(type="detector", detector=_REGEX)
        guard = config.build()
        assert isinstance(guard, DetectorGuardRail)
        assert isinstance(guard.detector, RegexDetector)

    def test_moderation_guard_builds_with_env_credentials(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The moderation guard config builds a ModerationGuardRail from the env."""
        monkeypatch.setenv("MISTRAL_API_KEY", "test")
        config = ModerationGuardRailConfig(type="moderation", threshold=0.3)
        guard = config.build()
        assert isinstance(guard, ModerationGuardRail)
        assert guard.threshold == 0.3

    def test_moderation_guard_requires_the_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The moderation guard build raises when the API key env var is unset."""
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        config = ModerationGuardRailConfig(type="moderation")
        with pytest.raises(ConfigError):
            config.build()

    def test_moderation_rejects_out_of_range_threshold(self) -> None:
        """A moderation threshold outside zero to one fails validation."""
        with pytest.raises(ValidationError):
            ModerationGuardRailConfig(type="moderation", threshold=1.5)

    def test_llm_guard_parses_and_dispatches(self) -> None:
        """The llm type dispatches to LLMGuardRailConfig without building it."""
        adapter = TypeAdapter(GuardConfig)
        parsed = adapter.validate_python(
            {"type": "llm", "model": "openai:gpt-4o-mini", "labels": ["PERSON"]}
        )
        assert isinstance(parsed, LLMGuardRailConfig)
        assert parsed.model == "openai:gpt-4o-mini"

    def test_union_dispatches_detector(self) -> None:
        """The detector type dispatches to DetectorGuardRailConfig."""
        adapter = TypeAdapter(GuardConfig)
        parsed = adapter.validate_python({"type": "detector", "detector": _REGEX})
        assert isinstance(parsed, DetectorGuardRailConfig)


class TestOverrideConfig:
    def test_builds_a_detection_override(self) -> None:
        """The override config builds a DetectionOverride with default strategies."""
        config = OverrideConfig(blacklist=_REGEX)
        override = config.build()
        assert isinstance(override, DetectionOverride)
        assert isinstance(override.blacklist, RegexDetector)
        assert override.whitelist is None
        assert override.blacklist_strategy is BlacklistStrategy.EXACT
        assert override.whitelist_strategy is WhitelistStrategy.RESPECT_PROVENANCE
        assert override.conflict_strategy is OverrideConflictStrategy.WHITELIST_WINS

    def test_builds_with_both_lists(self) -> None:
        """The override config builds both a whitelist and a blacklist detector."""
        config = OverrideConfig(whitelist=_REGEX, blacklist=_REGEX)
        override = config.build()
        assert isinstance(override.whitelist, RegexDetector)
        assert isinstance(override.blacklist, RegexDetector)

    def test_parses_strategies_from_strings(self) -> None:
        """The strategy fields parse from their TOML string values."""
        config = OverrideConfig(
            whitelist=_REGEX,
            blacklist_strategy="value",
            whitelist_strategy="force",
            conflict_strategy="blacklist_wins",
        )
        assert config.blacklist_strategy is BlacklistStrategy.VALUE
        assert config.whitelist_strategy is WhitelistStrategy.FORCE
        assert config.conflict_strategy is OverrideConflictStrategy.BLACKLIST_WINS

"""Tests for the guard and override config models."""

import re

import pytest
from pydantic import TypeAdapter, ValidationError

from piighost.components.detector import RegexDetector
from piighost.components.guard import (
    DetectorGuardRail,
    ModerationGuardRail,
)
from piighost.components.override import (
    AllowListStrategy,
    DenyListStrategy,
    DetectionOverride,
    OverrideConflictStrategy,
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
"""An inline regex detector config, reused as the nested detector under test."""


class TestGuardConfig:
    def test_detector_guard_builds_over_its_detector(self) -> None:
        """The detector guard config builds a DetectorGuardRail on its detector."""
        config = DetectorGuardRailConfig(type="detector", detector=_REGEX)
        guard = config.build()
        assert isinstance(guard, DetectorGuardRail)
        assert isinstance(guard.detector, RegexDetector)

    @pytest.mark.parametrize("ignore", [True, False])
    def test_detector_guard_forwards_the_placeholder_switch(self, ignore: bool) -> None:
        """ignore_placeholders reaches the built guard, on by default."""
        config = DetectorGuardRailConfig(
            type="detector",
            detector=_REGEX,
            ignore_placeholders=ignore,
        )
        guard = config.build()
        assert isinstance(guard, DetectorGuardRail)
        assert guard.ignore_placeholders is ignore

    def test_detector_guard_ignores_placeholders_by_default(self) -> None:
        """A detector guard config with no switch drops placeholder detections."""
        config = DetectorGuardRailConfig(type="detector", detector=_REGEX)
        assert config.ignore_placeholders is True

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
        config = OverrideConfig(allow_list=_REGEX)
        override = config.build()
        assert isinstance(override, DetectionOverride)
        assert isinstance(override.allow_list, RegexDetector)
        assert override.deny_list is None
        assert override.allow_list_strategy is AllowListStrategy.VALUE
        assert override.deny_list_strategy is DenyListStrategy.RESPECT_PROVENANCE
        assert override.conflict_strategy is OverrideConflictStrategy.DENY_LIST_WINS

    def test_builds_with_both_lists(self) -> None:
        """The override config builds both a deny list and an allow list detector."""
        config = OverrideConfig(deny_list=_REGEX, allow_list=_REGEX)
        override = config.build()
        assert isinstance(override, DetectionOverride)
        assert isinstance(override.deny_list, RegexDetector)
        assert isinstance(override.allow_list, RegexDetector)

    def test_parses_strategies_from_strings(self) -> None:
        """The strategy fields parse from their TOML string values."""
        config = OverrideConfig(
            deny_list=_REGEX,
            allow_list_strategy="value",
            deny_list_strategy="force",
            conflict_strategy="allow_list_wins",
        )
        assert config.allow_list_strategy is AllowListStrategy.VALUE
        assert config.deny_list_strategy is DenyListStrategy.FORCE
        assert config.conflict_strategy is OverrideConflictStrategy.ALLOW_LIST_WINS

    @pytest.mark.parametrize(
        ("old_key", "message"),
        [
            pytest.param(
                "whitelist",
                "'whitelist' was renamed 'deny_list' in piighost 2.0 "
                "(values always masked)",
                id="whitelist",
            ),
            pytest.param(
                "blacklist",
                "'blacklist' was renamed 'allow_list' in piighost 2.0 "
                "(values always left in clear)",
                id="blacklist",
            ),
            pytest.param(
                "whitelist_strategy",
                "'whitelist_strategy' was renamed 'deny_list_strategy'",
                id="whitelist_strategy",
            ),
            pytest.param(
                "blacklist_strategy",
                "'blacklist_strategy' was renamed 'allow_list_strategy'",
                id="blacklist_strategy",
            ),
        ],
    )
    def test_refuses_a_1x_key_with_its_new_name(
        self, old_key: str, message: str
    ) -> None:
        """A 1.x key fails validation, naming the 2.0 key, never reinterpreted."""
        with pytest.raises(ValidationError, match=re.escape(message)):
            OverrideConfig.model_validate({old_key: _REGEX})

    @pytest.mark.parametrize(
        ("old_value", "new_value"),
        [
            pytest.param("whitelist_wins", "deny_list_wins", id="whitelist_wins"),
            pytest.param("blacklist_wins", "allow_list_wins", id="blacklist_wins"),
        ],
    )
    def test_refuses_a_1x_conflict_value_with_its_new_name(
        self, old_value: str, new_value: str
    ) -> None:
        """A 1.x conflict strategy value fails validation, naming the 2.0 value."""
        with pytest.raises(
            ValidationError,
            match=f"'{old_value}' was renamed '{new_value}' in piighost 2.0",
        ):
            OverrideConfig(conflict_strategy=old_value)

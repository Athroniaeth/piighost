"""Detection override configuration model."""

from pydantic import field_validator, model_validator

from piighost.components.override.base import AnyDetectionOverride
from piighost.components.override.strategy import (
    AllowListStrategy,
    DenyListStrategy,
    OverrideConflictStrategy,
)
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.detector import DetectorConfig

_RENAMED_KEYS: dict[str, tuple[str, str]] = {
    "whitelist": ("deny_list", "values always masked"),
    "blacklist": ("allow_list", "values always left in clear"),
    "whitelist_strategy": ("deny_list_strategy", "the strategy of the deny list"),
    "blacklist_strategy": ("allow_list_strategy", "the strategy of the allow list"),
}
"""The override keys piighost 1.x read, each with its 2.0 name and meaning.

In 1.x the whitelist forced masking and the blacklist left values in clear, the
opposite of the usual sense. A 1.x config is refused with the new name rather
than reinterpreted, since a whitelist silently read as an allow list would leak
every value it was meant to mask.
"""

_RENAMED_CONFLICT_VALUES: dict[str, str] = {
    "whitelist_wins": "deny_list_wins",
    "blacklist_wins": "allow_list_wins",
}
"""The conflict strategy values piighost 1.x read, each with its 2.0 value."""


class OverrideConfig(_ComponentConfig):
    """Config for the detection override, a deny list and an allow list detector.

    The deny list holds what is always masked, the allow list what is always
    left in clear. Their 1.x names, whitelist and blacklist, are refused with
    the name that replaces them.

    Attributes:
        deny_list: A detector whose hits are always masked, forced into the set
            and replacing any detection they overlap, or None.
        allow_list: A detector whose hits are always left in clear, invalidating
            existing detections per the allow list strategy, or None.
        allow_list_strategy: How an allow list hit invalidates, exact span, value, or overlap.
        deny_list_strategy: Whether a deny list hit respects assistant provenance or forces it.
        conflict_strategy: Which list wins when the two contradict each other.
    """

    deny_list: DetectorConfig | None = None
    allow_list: DetectorConfig | None = None
    allow_list_strategy: AllowListStrategy = AllowListStrategy.VALUE
    deny_list_strategy: DenyListStrategy = DenyListStrategy.RESPECT_PROVENANCE
    conflict_strategy: OverrideConflictStrategy = (
        OverrideConflictStrategy.DENY_LIST_WINS
    )

    @model_validator(mode="before")
    @classmethod
    def _refuse_renamed_keys(cls, data: object) -> object:
        """Refuse a 1.x key, naming the 2.0 key that replaces it.

        Without this the key fails as a bare extra field, and the message does
        not say that whitelist became deny_list and blacklist became allow_list,
        the reverse of what the old names suggest to most readers.
        """
        if not isinstance(data, dict):
            return data
        renamed = [key for key in _RENAMED_KEYS if key in data]
        if renamed:
            messages = [
                f"{key!r} was renamed {_RENAMED_KEYS[key][0]!r} in piighost 2.0 "
                f"({_RENAMED_KEYS[key][1]})"
                for key in renamed
            ]
            raise ValueError("; ".join(messages))
        return data

    @field_validator("conflict_strategy", mode="before")
    @classmethod
    def _refuse_renamed_conflict_values(cls, value: object) -> object:
        """Refuse a 1.x conflict strategy value, naming the 2.0 value."""
        if isinstance(value, str) and value in _RENAMED_CONFLICT_VALUES:
            raise ValueError(
                f"conflict_strategy {value!r} was renamed "
                f"{_RENAMED_CONFLICT_VALUES[value]!r} in piighost 2.0"
            )
        return value

    def build(self) -> AnyDetectionOverride:
        """Build a DetectionOverride from the lists and the strategies."""
        from piighost.components.override.detector import DetectionOverride

        deny_list = self.deny_list.build() if self.deny_list else None
        allow_list = self.allow_list.build() if self.allow_list else None
        return DetectionOverride(
            deny_list=deny_list,
            allow_list=allow_list,
            allow_list_strategy=self.allow_list_strategy,
            deny_list_strategy=self.deny_list_strategy,
            conflict_strategy=self.conflict_strategy,
        )

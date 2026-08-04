"""Detection override configuration model."""

from piighost.components.override.base import AnyDetectionOverride
from piighost.components.override.strategy import (
    BlacklistStrategy,
    OverrideConflictStrategy,
    WhitelistStrategy,
)
from piighost.config.models.common import _ComponentConfig
from piighost.config.models.detector import DetectorConfig


class OverrideConfig(_ComponentConfig):
    """Config for the detection override, a whitelist and a blacklist detector.

    Attributes:
        whitelist: A detector whose hits are forced into the set, replacing any
            detection they overlap, or None.
        blacklist: A detector whose hits invalidate existing detections, per the
            blacklist strategy, or None.
        blacklist_strategy: How a blacklist hit invalidates, exact span, value, or overlap.
        whitelist_strategy: Whether a whitelist hit respects assistant provenance or forces it.
        conflict_strategy: Which list wins when the two contradict each other.
    """

    whitelist: DetectorConfig | None = None
    blacklist: DetectorConfig | None = None
    blacklist_strategy: BlacklistStrategy = BlacklistStrategy.EXACT
    whitelist_strategy: WhitelistStrategy = WhitelistStrategy.RESPECT_PROVENANCE
    conflict_strategy: OverrideConflictStrategy = (
        OverrideConflictStrategy.WHITELIST_WINS
    )

    def build(self) -> AnyDetectionOverride:
        """Build a DetectionOverride from the lists and the strategies."""
        from piighost.components.override.detector import DetectionOverride

        whitelist = self.whitelist.build() if self.whitelist else None
        blacklist = self.blacklist.build() if self.blacklist else None
        return DetectionOverride(
            whitelist=whitelist,
            blacklist=blacklist,
            blacklist_strategy=self.blacklist_strategy,
            whitelist_strategy=self.whitelist_strategy,
            conflict_strategy=self.conflict_strategy,
        )

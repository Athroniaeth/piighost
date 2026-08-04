"""Detector-driven override: force and clear detections by server decision."""

from collections.abc import Callable

from piighost.components.detector.base import AnyDetector
from piighost.components.override.strategy import (
    BlacklistStrategy,
    OverrideConflictStrategy,
    WhitelistStrategy,
)
from piighost.exceptions import ConflictingOverrideError
from piighost.models import Detection


def _exact_invalidated(detection: Detection, cleared: list[Detection]) -> bool:
    """Whether a cleared detection matches this one span for span, label for label."""
    return any(
        cleared_one.span == detection.span and cleared_one.label == detection.label
        for cleared_one in cleared
    )


def _value_invalidated(detection: Detection, cleared: list[Detection]) -> bool:
    """Whether any cleared detection carries this one's casefolded text."""
    values = {cleared_one.text.casefold() for cleared_one in cleared}
    return detection.text.casefold() in values


def _overlap_invalidated(detection: Detection, cleared: list[Detection]) -> bool:
    """Whether any cleared detection overlaps this one, labels ignored."""
    return any(detection.span.overlaps(cleared_one.span) for cleared_one in cleared)


_BLACKLIST_RULES: dict[
    BlacklistStrategy, Callable[[Detection, list[Detection]], bool]
] = {
    BlacklistStrategy.EXACT: _exact_invalidated,
    BlacklistStrategy.VALUE: _value_invalidated,
    BlacklistStrategy.OVERLAP: _overlap_invalidated,
}
"""One invalidation predicate per blacklist strategy."""


class DetectionOverride:
    """Force and clear detections by server decision, driven by detectors.

    The whitelist is a detector whose detections are added no matter what,
    replacing any detection they overlap, so the server's value and label win
    over the primary detector's reading. The blacklist is a detector whose
    detections invalidate existing ones, per the blacklist strategy. Because the
    pipelines apply this component after every detection read and before every
    memory write, both lists also trump a human's corrected set.

    This is the production way to force values: a whitelist built on an
    ExactMatchDetector or a RegexDetector survives HITL corrections, where
    ExactMatchDetector used alone as a primary detector is first a test helper.

    Attributes:
        whitelist: The detector whose detections are forced in, or None.
        blacklist: The detector whose detections invalidate, or None.
        blacklist_strategy: How a blacklist detection invalidates.
        whitelist_strategy: Whether the whitelist outranks assistant provenance.
        conflict_strategy: Who wins when the two lists contradict each other.
    """

    def __init__(
        self,
        whitelist: AnyDetector | None = None,
        blacklist: AnyDetector | None = None,
        blacklist_strategy: BlacklistStrategy = BlacklistStrategy.EXACT,
        whitelist_strategy: WhitelistStrategy = WhitelistStrategy.RESPECT_PROVENANCE,
        conflict_strategy: OverrideConflictStrategy = (
            OverrideConflictStrategy.WHITELIST_WINS
        ),
    ) -> None:
        """Store the two list detectors and their strategies."""
        self.whitelist = whitelist
        self.blacklist = blacklist
        self.blacklist_strategy = blacklist_strategy
        self.whitelist_strategy = whitelist_strategy
        self.conflict_strategy = conflict_strategy

    async def apply(self, text: str, detections: list[Detection]) -> list[Detection]:
        """Return the detections with the server lists imposed.

        The conflict strategy decides the application order: WHITELIST_WINS
        clears first and forces last, BLACKLIST_WINS forces first and clears
        last, RAISE refuses any collision between the two lists' outputs before
        applying either, then applies clear-then-force like WHITELIST_WINS,
        the two orders being equivalent once no collision exists.
        """
        forced = await self.whitelist.detect(text) if self.whitelist else []
        cleared = await self.blacklist.detect(text) if self.blacklist else []

        if self.conflict_strategy is OverrideConflictStrategy.RAISE:
            self._refuse_collisions(forced, cleared)

        if self.conflict_strategy is OverrideConflictStrategy.BLACKLIST_WINS:
            forced_first = self._force(detections, forced)
            return self._clear(forced_first, cleared)

        kept = self._clear(detections, cleared)
        return self._force(kept, forced)

    async def cleared_values(self, text: str) -> frozenset[str]:
        """Return the casefolded values the blacklist matches in this text."""
        if self.blacklist is None:
            return frozenset()
        cleared = await self.blacklist.detect(text)
        return frozenset(detection.text.casefold() for detection in cleared)

    async def forces_value(self, value: str) -> bool:
        """Return whether the whitelist forces this value to a token."""
        if self.whitelist is None:
            return False
        if self.whitelist_strategy is WhitelistStrategy.RESPECT_PROVENANCE:
            return False
        matches = await self.whitelist.detect(value)
        return any(match.text.casefold() == value.casefold() for match in matches)

    def _force(
        self, detections: list[Detection], forced: list[Detection]
    ) -> list[Detection]:
        """Add the whitelist detections, replacing any detection they overlap."""
        if not forced:
            return detections
        kept = [
            detection
            for detection in detections
            if not any(detection.overlaps(forced_one) for forced_one in forced)
        ]
        combined = kept + list(forced)
        return sorted(combined)

    def _clear(
        self, detections: list[Detection], cleared: list[Detection]
    ) -> list[Detection]:
        """Drop the detections the blacklist invalidates, per the strategy."""
        if not cleared:
            return detections
        invalidated = _BLACKLIST_RULES[self.blacklist_strategy]
        return [
            detection for detection in detections if not invalidated(detection, cleared)
        ]

    def _refuse_collisions(
        self, forced: list[Detection], cleared: list[Detection]
    ) -> None:
        """Raise when the two lists contradict each other on a span."""
        for forced_one in forced:
            for cleared_one in cleared:
                if forced_one.span.overlaps(cleared_one.span):
                    raise ConflictingOverrideError(
                        f"Overrides contradict each other on '{forced_one.text}': "
                        "a whitelisted span overlaps a blacklisted one."
                    )

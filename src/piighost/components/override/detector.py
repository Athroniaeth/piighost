"""Detector-driven override: force and clear detections by server decision."""

from collections.abc import Callable

from piighost.components.detector.base import AnyDetector
from piighost.components.override.strategy import (
    AllowListStrategy,
    DenyListStrategy,
    OverrideConflictStrategy,
)
from piighost.exceptions import ConflictingOverrideError
from piighost.models import Detection
from piighost.text import value_key


def _exact_invalidated(detection: Detection, cleared: list[Detection]) -> bool:
    """Whether a cleared detection matches this one span for span, label for label."""
    return any(
        cleared_one.span == detection.span and cleared_one.label == detection.label
        for cleared_one in cleared
    )


def _value_invalidated(detection: Detection, cleared: list[Detection]) -> bool:
    """Whether any cleared detection carries this one's value, by value key."""
    values = {value_key(cleared_one.text) for cleared_one in cleared}
    return value_key(detection.text) in values


def _overlap_invalidated(detection: Detection, cleared: list[Detection]) -> bool:
    """Whether any cleared detection overlaps this one, labels ignored."""
    return any(detection.span.overlaps(cleared_one.span) for cleared_one in cleared)


_ALLOW_LIST_RULES: dict[
    AllowListStrategy, Callable[[Detection, list[Detection]], bool]
] = {
    AllowListStrategy.EXACT: _exact_invalidated,
    AllowListStrategy.VALUE: _value_invalidated,
    AllowListStrategy.OVERLAP: _overlap_invalidated,
}
"""One invalidation predicate per allow list strategy."""


class DetectionOverride:
    """Force and clear detections by server decision, driven by detectors.

    The deny list holds what is always masked: a detector whose detections are
    added no matter what, replacing any detection they overlap, so the server's
    value and label win over the primary detector's reading. The allow list
    holds what is always left in clear: a detector whose detections invalidate
    existing ones, per the allow list strategy. Because the
    pipelines apply this component after every detector call and before every
    memory write, both lists also trump a human's corrected set. A message
    already in the conversation memory keeps the detections it was stored with,
    so a list changed later applies to the messages detected after the change.

    This is the production way to force values: a deny list built on an
    ExactMatchDetector or a RegexDetector survives HITL corrections, where
    ExactMatchDetector used alone as a primary detector is first a test helper.

    Attributes:
        deny_list: The detector whose detections are always masked, or None.
        allow_list: The detector whose detections are always left in clear, or
            None.
        allow_list_strategy: How an allow list detection invalidates.
        deny_list_strategy: Whether the deny list outranks assistant provenance.
        conflict_strategy: Who wins when the two lists contradict each other.
    """

    def __init__(
        self,
        deny_list: AnyDetector | None = None,
        allow_list: AnyDetector | None = None,
        allow_list_strategy: AllowListStrategy = AllowListStrategy.VALUE,
        deny_list_strategy: DenyListStrategy = DenyListStrategy.RESPECT_PROVENANCE,
        conflict_strategy: OverrideConflictStrategy = (
            OverrideConflictStrategy.DENY_LIST_WINS
        ),
    ) -> None:
        """Store the two list detectors and their strategies."""
        self.deny_list = deny_list
        self.allow_list = allow_list
        self.allow_list_strategy = allow_list_strategy
        self.deny_list_strategy = deny_list_strategy
        self.conflict_strategy = conflict_strategy

    async def apply(self, text: str, detections: list[Detection]) -> list[Detection]:
        """Return the detections with the server lists imposed.

        The conflict strategy decides the application order: DENY_LIST_WINS
        clears first and forces last, ALLOW_LIST_WINS forces first and clears
        last, RAISE refuses any collision between the two lists' outputs before
        applying either, then applies clear-then-force like DENY_LIST_WINS,
        the two orders being equivalent once no collision exists.
        """
        forced = await self.deny_list.detect(text) if self.deny_list else []
        cleared = await self.allow_list.detect(text) if self.allow_list else []

        if self.conflict_strategy is OverrideConflictStrategy.RAISE:
            self._refuse_collisions(forced, cleared)

        if self.conflict_strategy is OverrideConflictStrategy.ALLOW_LIST_WINS:
            forced_first = self._force(detections, forced)
            return self._clear(forced_first, cleared)

        kept = self._clear(detections, cleared)
        return self._force(kept, forced)

    async def cleared_values(self, text: str) -> frozenset[str]:
        """Return the value keys of what the allow list matches in this text."""
        if self.allow_list is None:
            return frozenset()
        cleared = await self.allow_list.detect(text)
        return frozenset(value_key(detection.text) for detection in cleared)

    async def forces_value(self, value: str) -> bool:
        """Return whether the deny list forces this value to a token."""
        if self.deny_list is None:
            return False
        if self.deny_list_strategy is DenyListStrategy.RESPECT_PROVENANCE:
            return False
        matches = await self.deny_list.detect(value)
        return any(value_key(match.text) == value_key(value) for match in matches)

    def _force(
        self, detections: list[Detection], forced: list[Detection]
    ) -> list[Detection]:
        """Add the deny list detections, replacing any detection they overlap.

        The result is in position order. It is sorted on the span alone, so two
        detections on one span stay in detector order, which the overlap
        resolver breaks a tie with.
        """
        if not forced:
            return detections
        kept = [
            detection
            for detection in detections
            if not any(detection.overlaps(forced_one) for forced_one in forced)
        ]
        combined = kept + list(forced)
        return sorted(combined, key=lambda detection: detection.span)

    def _clear(
        self, detections: list[Detection], cleared: list[Detection]
    ) -> list[Detection]:
        """Drop the detections the allow list invalidates, per the strategy."""
        if not cleared:
            return detections
        invalidated = _ALLOW_LIST_RULES[self.allow_list_strategy]
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
                        "a span on the deny list overlaps one on the allow list."
                    )

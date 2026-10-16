"""Merge overlap resolver: keep the union where spans overlap."""

from piighost.components.overlap_resolver.base import BaseOverlapResolver
from piighost.models import Detection, Span


def _surest(detection: Detection) -> tuple[float, int, Span]:
    """Sort key ordering detections most confident, then widest, then first.

    A stable sort on it keeps the earliest detector's detection on a true tie,
    since a conflict group is in detector order.
    """
    span = detection.span
    return -detection.confidence, span.start - span.end, span


class MergeOverlapResolver(BaseOverlapResolver):
    """Replace every group of overlapping detections by the span they cover together.

    Keeping only the most confident detection of a group can leave text in
    clear. A regex at confidence 1.0 that found "Wirth" beats a model that
    found "Loni M. Wirth" at 0.7, and "Loni M." is sent as it is. This resolver
    hides the union instead, so no character any detector flagged is left out.
    The merged detection takes the label and confidence of its surest member:
    the most confident, then the widest, then the earliest span, then the
    earliest detector. The width comes before the position because the union
    is named after what it holds. A phone pattern that matched the first nine
    digits of a fourteen-digit company number does not name the whole number.

    The members of a group overlap one another in a chain, so their union is one
    contiguous range, and its text is rebuilt from theirs.

    Some detections can be preferred, so they name the union before any other,
    whatever their confidence. A human correction is preferred this way: the
    human names the span over any detector, while the union still hides every
    character a detector flagged. Among preferred members, and when none is
    present, the surest rule above applies.

    Attributes:
        preferred: The detections that name a union they belong to first.
    """

    def __init__(self, preferred: frozenset[Detection] = frozenset()) -> None:
        """Store the detections that name their union first, none by default."""
        self.preferred = preferred

    def _reduce(self, conflicting: list[Detection]) -> list[Detection]:
        """Merge the group into one detection spanning all of it."""
        if len(conflicting) == 1:
            return conflicting
        start = min(detection.span.start for detection in conflicting)
        end = max(detection.span.end for detection in conflicting)
        characters = [""] * (end - start)
        for detection in conflicting:
            offset = detection.span.start - start
            characters[offset : offset + len(detection.text)] = detection.text
        namer = min(conflicting, key=self._naming_order)
        span = Span(start, end)
        text = "".join(characters)
        merged = Detection(
            span=span,
            text=text,
            label=namer.label,
            confidence=namer.confidence,
        )
        return [merged]

    def _naming_order(self, detection: Detection) -> tuple[bool, float, int, Span]:
        """Sort key ordering preferred detections first, then the surest."""
        return detection not in self.preferred, *_surest(detection)

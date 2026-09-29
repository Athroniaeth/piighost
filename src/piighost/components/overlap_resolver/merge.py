"""Merge overlap resolver: keep the union where spans overlap."""

from piighost.components.overlap_resolver.base import BaseOverlapResolver
from piighost.components.overlap_resolver.confidence import _by_confidence
from piighost.models import Detection, Span


class MergeOverlapResolver(BaseOverlapResolver):
    """Replace every group of overlapping detections by the span they cover together.

    Keeping only the most confident detection of a group can leave text in
    clear. A regex at confidence 1.0 that found "Wirth" beats a model that
    found "Loni M. Wirth" at 0.7, and "Loni M." is sent as it is. This resolver
    hides the union instead, so no character any detector flagged is left out.
    The merged detection takes the label and confidence of the member the
    confidence resolver would keep first: the most confident, then the earliest
    span, then the earliest detector.

    The members of a group overlap one another in a chain, so their union is one
    contiguous range, and its text is rebuilt from theirs.
    """

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
        surest = min(conflicting, key=_by_confidence)
        span = Span(start, end)
        text = "".join(characters)
        merged = Detection(
            span=span,
            text=text,
            label=surest.label,
            confidence=surest.confidence,
        )
        return [merged]

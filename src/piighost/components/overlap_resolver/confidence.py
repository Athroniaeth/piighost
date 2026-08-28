"""Confidence overlap resolver: keep the most confident where spans overlap."""

from piighost.components.overlap_resolver.base import BaseOverlapResolver
from piighost.models import Detection, Span


def _by_confidence(detection: Detection) -> tuple[float, Span]:
    """Sort key ordering detections most confident first, then by position."""
    return -detection.confidence, detection.span


class ConfidenceOverlapResolver(BaseOverlapResolver):
    """Keep the most confident detections where spans overlap."""

    def _reduce(self, conflicting: list[Detection]) -> list[Detection]:
        """Greedily keep the most confident, non-overlapping detections."""
        kept: list[Detection] = []
        ordered = sorted(conflicting, key=_by_confidence)

        for detection in ordered:
            if any(detection.overlaps(other) for other in kept):
                continue
            kept.append(detection)
        return kept

"""Overlap resolvers: keep one detection where spans overlap."""

from piighost.models import Detection, Span


def _confidence_then_position(detection: Detection) -> tuple[float, Span]:
    """Sort key ordering detections most confident first, then by position."""
    return -detection.confidence, detection.span


class ConfidenceOverlapResolver:
    """Resolve overlapping detections by keeping the most confident.

    Greedy: it considers detections from most to least confident and keeps each
    one unless it overlaps a detection already kept. The result is a set of
    non-overlapping detections, returned in position order.
    """

    def resolve(self, detections: list[Detection]) -> list[Detection]:
        """Return non-overlapping detections, keeping the most confident."""
        kept: list[Detection] = []
        ordered = sorted(detections, key=_confidence_then_position)

        for detection in ordered:
            if any(detection.overlaps(other) for other in kept):
                continue
            kept.append(detection)
        return sorted(kept)

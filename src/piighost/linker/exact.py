"""Exact entity linker: group detections by case-insensitive value and label."""

from piighost.linker.base import BaseEntityLinker
from piighost.models import Detection


class ExactEntityLinker(BaseEntityLinker):
    """Group detections that share a case-insensitive value and label.

    Two detections belong to the same entity when their texts are equal under
    casefold and their labels match, so Patrick and patrick under PERSON become
    one entity while the same text under another label stays separate. Entities
    and their detections keep first-occurrence order, so an entity's canonical
    value is the first spelling seen.
    """

    def _key(self, detection: Detection) -> tuple[str, str]:
        """Group by the casefolded text paired with the label."""
        return (detection.text.casefold(), detection.label)

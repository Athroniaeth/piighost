"""Exact entity linker: group detections by case-insensitive value."""

from piighost.components.linker.base import BaseEntityLinker
from piighost.models import Detection
from piighost.text import value_key


class ExactEntityLinker(BaseEntityLinker):
    """Group detections that share a case-insensitive value, whatever their label.

    Two detections belong to the same entity when their texts share a value key
    (the same words, whatever the spaces between them, under casefold), so
    Patrick and patrick become one entity. The label does not split a value:
    two detectors that name one value differently, say USERNAME and PERSON,
    still give it one entity and one placeholder, the same identity rule the
    overrides, the conversation memory and the provenance follow. Entities and
    their detections keep first-occurrence order, so an entity's canonical value
    is the first spelling seen and its label the first label seen.
    """

    def _key(self, detection: Detection) -> str:
        """Group by the value key of the text alone."""
        return value_key(detection.text)

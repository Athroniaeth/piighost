"""Entity linker abstractions: the port and a shared grouping template."""

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Hashable
from typing import Protocol, runtime_checkable

from piighost.models import Detection, Entity


@runtime_checkable
class AnyEntityLinker(Protocol):
    """A component that groups detections referring to the same value.

    Given the detections found in a text, it partitions them into entities so
    every occurrence of one value shares a single placeholder. It only groups
    the detections it is given; finding missed occurrences is the expander's
    job.
    """

    def link(self, detections: list[Detection]) -> list[Entity]:
        """Group detections into entities, one per distinct value.

        Args:
            detections: The detections to group.

        Returns:
            One entity per distinct value, each grouping its occurrences.
        """
        ...


class BaseEntityLinker(ABC):
    """Group detections by a subclass-defined key, one entity per key.

    The skeleton lives here: compute a key for each detection, gather the
    detections sharing a key in first-occurrence order, and build one entity per
    group. A subclass defines _key, the rule that decides which detections
    belong together, such as a case-insensitive value paired with the label.
    """

    def link(self, detections: list[Detection]) -> list[Entity]:
        """Group detections into one entity per distinct key."""
        groups: dict[Hashable, list[Detection]] = defaultdict(list)

        for detection in detections:
            key = self._key(detection)
            groups[key].append(detection)

        return [Entity(tuple(group)) for group in groups.values()]

    @abstractmethod
    def _key(self, detection: Detection) -> Hashable:
        """Return the grouping key that decides an entity's membership."""
        ...

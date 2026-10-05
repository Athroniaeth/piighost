from abc import ABC, abstractmethod
from collections.abc import Hashable

from piighost.models import Detection, Entity


# isort: split
# --8<-- [start:example]
class BaseEntityLinker(ABC):
    def link(self, detections: list[Detection]) -> list[Entity]:
        # common skeleton: group by key
        ...

    @abstractmethod
    def _key(self, detection: Detection) -> Hashable:
        # only varying step, defined by the subclass
        ...


# --8<-- [end:example]

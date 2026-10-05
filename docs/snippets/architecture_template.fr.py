from abc import ABC, abstractmethod
from collections.abc import Hashable

from piighost.models import Detection, Entity


# isort: split
# --8<-- [start:example]
class BaseEntityLinker(ABC):
    def link(self, detections: list[Detection]) -> list[Entity]:
        # squelette commun : grouper par clé
        ...

    @abstractmethod
    def _key(self, detection: Detection) -> Hashable:
        # seul pas variable, défini par la sous-classe
        ...


# --8<-- [end:example]

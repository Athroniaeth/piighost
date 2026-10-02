from collections.abc import Mapping
from typing import Protocol

from piighost.components.guard.base import GuardVerdict
from piighost.components.placeholder.tags import PreservationT_co
from piighost.models import Detection, Entity


# isort: split
# --8<-- [start:detector]
class AnyDetector(Protocol):
    async def detect(self, text: str) -> list[Detection]: ...


# --8<-- [end:detector]


# isort: split
# --8<-- [start:overlap_resolver]
class AnyOverlapResolver(Protocol):
    def resolve(self, detections: list[Detection]) -> list[Detection]: ...


# --8<-- [end:overlap_resolver]


# isort: split
# --8<-- [start:expander]
class AnyDetectionExpander(Protocol):
    def expand(self, text: str, detections: list[Detection]) -> list[Detection]: ...


# --8<-- [end:expander]


# isort: split
# --8<-- [start:linker]
class AnyEntityLinker(Protocol):
    def link(self, detections: list[Detection]) -> list[Entity]: ...


# --8<-- [end:linker]


# isort: split
# --8<-- [start:entity_resolver]
class AnyEntityResolver(Protocol):
    def resolve(self, entities: list[Entity]) -> list[Entity]: ...


# --8<-- [end:entity_resolver]


# isort: split
# --8<-- [start:placeholder_factory]
class AnyPlaceholderFactory(Protocol[PreservationT_co]):
    def create(self, entities: list[Entity]) -> Mapping[Entity, PreservationT_co]: ...


# --8<-- [end:placeholder_factory]


# isort: split
# --8<-- [start:guard]
class AnyGuardRail(Protocol):
    async def check(self, text: str) -> GuardVerdict: ...


# --8<-- [end:guard]

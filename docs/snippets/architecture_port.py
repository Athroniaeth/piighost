from typing import Protocol, runtime_checkable

from piighost.models import Detection


# isort: split
# --8<-- [start:example]
@runtime_checkable
class AnyDetector(Protocol):
    async def detect(self, text: str) -> list[Detection]: ...


# --8<-- [end:example]

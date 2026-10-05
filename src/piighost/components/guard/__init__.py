"""Guard rails: classify anonymized output for residual PII.

base.py holds the AnyGuardRail port and the GuardVerdict it returns; concrete
guards live in sibling modules. DetectorGuardRail is stdlib and always
available. Gliner2GuardRail, ModerationGuardRail and LLMGuardRail need optional
dependencies, so they are imported lazily: reaching for one without its extra
raises a helpful ImportError, while importing this package never pulls the
optional package in.
"""

import importlib
from typing import TYPE_CHECKING, Any

from piighost.components.guard.base import AnyGuardRail, GuardVerdict
from piighost.components.guard.detector import DetectorGuardRail

if TYPE_CHECKING:
    from piighost.components.guard.gliner2 import Gliner2GuardRail
    from piighost.components.guard.llm import LLMGuardRail
    from piighost.components.guard.moderation import ModerationGuardRail

__all__ = [
    "AnyGuardRail",
    "DetectorGuardRail",
    "Gliner2GuardRail",
    "GuardVerdict",
    "LLMGuardRail",
    "ModerationGuardRail",
]


_LAZY_GUARDS: dict[str, str] = {
    "Gliner2GuardRail": "piighost.components.guard.gliner2",
    "ModerationGuardRail": "piighost.components.guard.moderation",
    "LLMGuardRail": "piighost.components.guard.llm",
}
"""Each guard behind an optional dependency, by name, with the module that holds it."""


def __getattr__(name: str) -> Any:
    """Import an optional guard on demand so its dependency stays optional."""
    if name not in _LAZY_GUARDS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(_LAZY_GUARDS[name]), name)

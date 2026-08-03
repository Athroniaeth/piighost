"""Guard rails: classify anonymized output for residual PII.

base.py holds the AnyGuardRail port and the GuardVerdict it returns; concrete
guards live in sibling modules. DetectorGuardRail is stdlib and always
available. ModerationGuardRail and LLMGuardRail need optional dependencies, so
they are imported lazily: reaching for one without its extra raises a helpful
ImportError, while importing this package never pulls the optional package in.
"""

from typing import Any

from piighost.components.guard.base import AnyGuardRail, GuardVerdict
from piighost.components.guard.detector import DetectorGuardRail

__all__ = [
    "AnyGuardRail",
    "DetectorGuardRail",
    "GuardVerdict",
    "LLMGuardRail",
    "ModerationGuardRail",
]


def __getattr__(name: str) -> Any:
    """Import an optional guard on demand so its dependency stays optional."""
    if name == "ModerationGuardRail":
        from piighost.components.guard.moderation import ModerationGuardRail

        return ModerationGuardRail
    if name == "LLMGuardRail":
        from piighost.components.guard.llm import LLMGuardRail

        return LLMGuardRail

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

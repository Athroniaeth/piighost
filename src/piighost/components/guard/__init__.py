"""Guard rails: classify anonymized output for residual PII.

base.py holds the AnyGuardRail port and the GuardVerdict it returns; concrete
guards live in sibling modules. DetectorGuardRail is stdlib and always
available. ModerationGuardRail needs the mistralai optional dependency, so it is
imported lazily: reaching for it without the extra raises a helpful ImportError,
while importing this package never pulls mistralai in.
"""

from typing import Any

from piighost.components.guard.base import AnyGuardRail, GuardVerdict
from piighost.components.guard.detector import DetectorGuardRail

__all__ = [
    "AnyGuardRail",
    "DetectorGuardRail",
    "GuardVerdict",
    "ModerationGuardRail",
]


def __getattr__(name: str) -> Any:
    """Import ModerationGuardRail on demand so its optional dependency stays optional."""
    if name == "ModerationGuardRail":
        from piighost.components.guard.moderation import ModerationGuardRail

        return ModerationGuardRail

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

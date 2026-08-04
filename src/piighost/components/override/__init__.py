"""Detection overrides: server lists that trump detection and user feedback.

base.py holds the AnyDetectionOverride port, strategy.py the blacklist and
conflict strategies, and DetectionOverride is the detector-driven
implementation. The package is pure, so everything is exported eagerly.
"""

from piighost.components.override.base import AnyDetectionOverride
from piighost.components.override.detector import DetectionOverride
from piighost.components.override.strategy import (
    BlacklistStrategy,
    OverrideConflictStrategy,
)

__all__ = [
    "AnyDetectionOverride",
    "BlacklistStrategy",
    "DetectionOverride",
    "OverrideConflictStrategy",
]

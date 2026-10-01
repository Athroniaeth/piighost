"""NER detectors: model-backed adapters over a shared label-mapping base.

BaseNERDetector holds the shared logic and imports nothing optional. Concrete
model-backed adapters, each behind its own optional extra, are added here as
they land, exposed lazily so a missing extra fails only on access.
BridgeDetector holds no model of its own and needs no extra, so it is eager.
"""

import importlib
from typing import TYPE_CHECKING, Any

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.components.detector.ner.bridge import (
    AnySpanRunner,
    BridgeDetector,
    OffsetUnit,
)

if TYPE_CHECKING:
    from piighost.components.detector.ner.gliner2 import (
        Gliner2Detector,
        Gliner2PiiDetector,
    )
    from piighost.components.detector.ner.presidio import PresidioDetector
    from piighost.components.detector.ner.spacy import SpacyDetector
    from piighost.components.detector.ner.transformers import TransformersDetector

__all__ = [
    "AnySpanRunner",
    "BaseNERDetector",
    "BridgeDetector",
    "Gliner2Detector",
    "Gliner2PiiDetector",
    "OffsetUnit",
    "PresidioDetector",
    "SpacyDetector",
    "TransformersDetector",
]


_LAZY_ADAPTERS: dict[str, str] = {
    "Gliner2Detector": "piighost.components.detector.ner.gliner2",
    "Gliner2PiiDetector": "piighost.components.detector.ner.gliner2",
    "PresidioDetector": "piighost.components.detector.ner.presidio",
    "SpacyDetector": "piighost.components.detector.ner.spacy",
    "TransformersDetector": "piighost.components.detector.ner.transformers",
}
"""Each adapter behind an optional extra, by name, with the module that holds it."""


def __getattr__(name: str) -> Any:
    """Import a NER adapter on demand so its optional extra stays optional."""
    if name not in _LAZY_ADAPTERS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(_LAZY_ADAPTERS[name]), name)

"""NER detectors: model-backed adapters over a shared label-mapping base.

BaseNERDetector holds the shared logic and imports nothing optional. Concrete
model-backed adapters, each behind its own optional extra, are added here as
they land, exposed lazily so a missing extra fails only on access.
"""

from typing import Any

from piighost.components.detector.ner.base import BaseNERDetector

__all__ = [
    "BaseNERDetector",
    "Gliner2Detector",
    "Gliner2PiiDetector",
    "PresidioDetector",
    "SpacyDetector",
    "TransformersDetector",
]


def __getattr__(name: str) -> Any:
    """Import a NER adapter on demand so its optional extra stays optional."""
    if name == "Gliner2Detector":
        from piighost.components.detector.ner.gliner2 import Gliner2Detector

        return Gliner2Detector
    if name == "Gliner2PiiDetector":
        from piighost.components.detector.ner.gliner2 import Gliner2PiiDetector

        return Gliner2PiiDetector
    if name == "PresidioDetector":
        from piighost.components.detector.ner.presidio import PresidioDetector

        return PresidioDetector
    if name == "SpacyDetector":
        from piighost.components.detector.ner.spacy import SpacyDetector

        return SpacyDetector
    if name == "TransformersDetector":
        from piighost.components.detector.ner.transformers import (
            TransformersDetector,
        )

        return TransformersDetector

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

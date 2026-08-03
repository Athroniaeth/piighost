"""NER detectors: model-backed adapters over a shared label-mapping base.

BaseNERDetector holds the shared logic and imports nothing optional. Concrete
model-backed adapters, each behind its own optional extra, are added here as
they land, exposed lazily so a missing extra fails only on access.
"""

from piighost.components.detector.ner.base import BaseNERDetector

__all__ = ["BaseNERDetector"]

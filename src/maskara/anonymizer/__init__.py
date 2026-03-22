"""Anonymization pipeline: detect, expand, replace, deanonymize."""

from maskara.anonymizer.anonymizer import Anonymizer
from maskara.anonymizer.detector import EntityDetector, GlinerDetector
from maskara.anonymizer.models import AnonymizationResult, Entity, Placeholder
from maskara.anonymizer.occurrence import OccurrenceFinder, RegexOccurrenceFinder
from maskara.anonymizer.placeholder import (
    CounterPlaceholderFactory,
    HashPlaceholderFactory,
    PlaceholderFactory,
)

__all__ = [
    "Anonymizer",
    "AnonymizationResult",
    "CounterPlaceholderFactory",
    "Entity",
    "EntityDetector",
    "GlinerDetector",
    "HashPlaceholderFactory",
    "OccurrenceFinder",
    "Placeholder",
    "PlaceholderFactory",
    "RegexOccurrenceFinder",
]

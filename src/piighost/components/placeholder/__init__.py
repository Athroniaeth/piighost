"""Placeholder factories: turn entities into replacement tokens.

base.py holds the AnyPlaceholderFactory port, generic on a phantom preservation
tag; tags.py holds those tags; concrete factories live in sibling modules.
"""

from piighost.components.placeholder.base import (
    AnyPlaceholderFactory,
    BaseCounterPlaceholderFactory,
    BaseDelimitedPlaceholderFactory,
)
from piighost.components.placeholder.label import LabelPlaceholderFactory
from piighost.components.placeholder.label_counter import LabelCounterPlaceholderFactory
from piighost.components.placeholder.label_hash import LabelHashPlaceholderFactory
from piighost.components.placeholder.mask import MaskPlaceholderFactory
from piighost.components.placeholder.redact import RedactPlaceholderFactory
from piighost.components.placeholder.streaming import PlaceholderStreamDecoder
from piighost.components.placeholder.tags import (
    PlaceholderPreservation,
    PreservesIdentity,
    PreservesIdentityOnly,
    PreservesLabel,
    PreservesLabeledIdentity,
    PreservesLabeledIdentityHashed,
    PreservesLabeledIdentityOpaque,
    PreservesLabeledIdentityRealistic,
    PreservesNothing,
    PreservesRecognizableIdentity,
    PreservesShape,
    Recognizable,
)

__all__ = [
    "AnyPlaceholderFactory",
    "BaseCounterPlaceholderFactory",
    "BaseDelimitedPlaceholderFactory",
    "LabelCounterPlaceholderFactory",
    "LabelHashPlaceholderFactory",
    "LabelPlaceholderFactory",
    "MaskPlaceholderFactory",
    "PlaceholderPreservation",
    "PlaceholderStreamDecoder",
    "PreservesIdentity",
    "PreservesIdentityOnly",
    "PreservesLabel",
    "PreservesLabeledIdentity",
    "PreservesLabeledIdentityHashed",
    "PreservesLabeledIdentityOpaque",
    "PreservesLabeledIdentityRealistic",
    "PreservesNothing",
    "PreservesRecognizableIdentity",
    "PreservesShape",
    "Recognizable",
    "RedactPlaceholderFactory",
]

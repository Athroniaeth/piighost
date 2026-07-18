"""Placeholder factories: turn entities into replacement tokens.

base.py holds the AnyPlaceholderFactory port, generic on a phantom preservation
tag; tags.py holds those tags; concrete factories live in sibling modules.
"""

from piighost.placeholder.base import AnyPlaceholderFactory
from piighost.placeholder.label import LabelPlaceholderFactory
from piighost.placeholder.label_counter import LabelCounterPlaceholderFactory
from piighost.placeholder.redact import RedactPlaceholderFactory
from piighost.placeholder.tags import (
    PlaceholderPreservation,
    PreservesIdentity,
    PreservesIdentityOnly,
    PreservesLabel,
    PreservesLabeledIdentity,
    PreservesLabeledIdentityFaker,
    PreservesLabeledIdentityHashed,
    PreservesLabeledIdentityOpaque,
    PreservesLabeledIdentityRealistic,
    PreservesNothing,
    PreservesShape,
)

__all__ = [
    "AnyPlaceholderFactory",
    "LabelCounterPlaceholderFactory",
    "LabelPlaceholderFactory",
    "PlaceholderPreservation",
    "PreservesIdentity",
    "PreservesIdentityOnly",
    "PreservesLabel",
    "PreservesLabeledIdentity",
    "PreservesLabeledIdentityFaker",
    "PreservesLabeledIdentityHashed",
    "PreservesLabeledIdentityOpaque",
    "PreservesLabeledIdentityRealistic",
    "PreservesNothing",
    "PreservesShape",
    "RedactPlaceholderFactory",
]

"""Common PII entity labels.

PIIGhost does not hardcode a fixed taxonomy of labels; detectors,
patterns, and validators can produce any ``str`` label that fits your
domain.  This module gathers the labels most frequently used across
the built-in components so callers can reference a single source of
truth instead of repeating magic strings.

Use them when wiring up detectors, placeholders, or assertions:

    >>> from piighost import labels
    >>> detector = ExactMatchDetector([("Patrick", labels.PERSON)])

The ``CommonLabel`` type alias is available for callers that want to
narrow their API surface to the canonical labels; it stays off the
public ``Detection.label`` field so custom labels keep working.
"""

from typing import Literal

PERSON = "PERSON"
LOCATION = "LOCATION"
ORGANIZATION = "ORGANIZATION"
EMAIL = "EMAIL"
PHONE = "PHONE"
DATE = "DATE"
ADDRESS = "ADDRESS"
IBAN = "IBAN"
CREDIT_CARD = "CREDIT_CARD"
IP_ADDRESS = "IP_ADDRESS"
URL = "URL"
API_KEY = "API_KEY"

CommonLabel = Literal[
    "PERSON",
    "LOCATION",
    "ORGANIZATION",
    "EMAIL",
    "PHONE",
    "DATE",
    "ADDRESS",
    "IBAN",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "URL",
    "API_KEY",
]
"""Type alias listing the labels exposed by this module.

Use it in your own signatures when you want static typing to catch
typos (``labels="PERSN"``) without forbidding custom labels on
``Detection`` itself.
"""

__all__ = [
    "ADDRESS",
    "API_KEY",
    "CREDIT_CARD",
    "CommonLabel",
    "DATE",
    "EMAIL",
    "IBAN",
    "IP_ADDRESS",
    "LOCATION",
    "ORGANIZATION",
    "PERSON",
    "PHONE",
    "URL",
]

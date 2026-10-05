"""Override strategies for the deny list, the allow list, and their conflicts.

The deny list holds the values always masked, the allow list the values always
left in clear.
"""

from enum import Enum


class DenyListStrategy(Enum):
    """Whether the deny list outranks assistant provenance for tokenization.

    RESPECT_PROVENANCE, the default: the deny list guarantees detection, but a
    value the assistant introduced first stays in clear. The model emitted it
    because it was useful in context and does not know it is confidential;
    replacing it with a token would both strip its world knowledge and signal
    that this precise value is sensitive. FORCE tokenizes a value on the deny list
    regardless of who introduced it first.
    """

    RESPECT_PROVENANCE = "respect_provenance"
    FORCE = "force"


class AllowListStrategy(Enum):
    """How an allow list detection invalidates an already-detected one.

    VALUE, the default, invalidates every detection carrying the same value,
    compared by value key, positions and labels ignored, the classic
    never-anonymize-this-value list. It is the default because an allow list
    names a value, and the label a caller writes beside it is a guess about
    what the primary detector will emit. EXACT invalidates only a detection
    with the identical span and label, the narrow rule to pick when the label
    is the point. OVERLAP invalidates any detection overlapping an allow list
    span, labels ignored, the most aggressive rule.
    """

    EXACT = "exact"
    VALUE = "value"
    OVERLAP = "overlap"


class OverrideConflictStrategy(Enum):
    """Who wins when the deny list and the allow list contradict each other.

    DENY_LIST_WINS, the default, applies the allow list to the primary
    detections first and adds the deny list last, so a contradicted value is
    anonymized, the fail-closed reading. ALLOW_LIST_WINS applies the deny list
    first and lets the allow list invalidate the result, forced values included.
    RAISE refuses a collision between the two lists' outputs with a
    ConflictingOverrideError.
    """

    DENY_LIST_WINS = "deny_list_wins"
    ALLOW_LIST_WINS = "allow_list_wins"
    RAISE = "raise"

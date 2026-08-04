"""Override strategies: how the blacklist invalidates and who wins a conflict."""

from enum import Enum


class BlacklistStrategy(Enum):
    """How a blacklist detection invalidates an already-detected one.

    EXACT, the default, invalidates only a detection with the identical span
    and label, the most predictable rule. VALUE invalidates every detection
    carrying the same casefolded text, positions and labels ignored, the
    classic never-anonymize-this-value list. OVERLAP invalidates any detection
    overlapping a blacklisted span, labels ignored, the most aggressive rule.
    """

    EXACT = "exact"
    VALUE = "value"
    OVERLAP = "overlap"


class OverrideConflictStrategy(Enum):
    """Who wins when the whitelist and the blacklist contradict each other.

    WHITELIST_WINS, the default, applies the blacklist to the primary
    detections first and adds the whitelist last, so a contradicted value is
    anonymized, the fail-closed reading. BLACKLIST_WINS applies the whitelist
    first and lets the blacklist invalidate the result, forced values included.
    RAISE refuses a collision between the two lists' outputs with a
    ConflictingOverrideError.
    """

    WHITELIST_WINS = "whitelist_wins"
    BLACKLIST_WINS = "blacklist_wins"
    RAISE = "raise"

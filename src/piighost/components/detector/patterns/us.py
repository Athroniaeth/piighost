"""US PII regex patterns.

Labels are prefixed with US_ so they do not collide with other packs. Pass them
to a RegexDetector.
"""

US_PATTERNS: dict[str, str] = {
    # SSN as NNN-NN-NNNN. Does not enforce SSA invalid ranges.
    "US_SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    # US phone, optional +1 prefix, optional parentheses, then 3-3-4 digits. The
    # (?<![\w+]) lookbehind anchors before a leading "+" or "(", which a plain
    # \b would miss, and (?!\d) stops a trailing digit run from extending it.
    "US_PHONE": (
        r"(?<![\w+])(?:\+?1[\s.-]?)?\(?[2-9]\d{2}\)?"
        r"[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
    ),
    # ZIP (5 digits) and ZIP+4 (5-4 digits).
    "US_ZIP": r"\b\d{5}(?:-\d{4})?\b",
}
"""United States PII patterns (SSN, phone, ZIP), labels prefixed with US_."""

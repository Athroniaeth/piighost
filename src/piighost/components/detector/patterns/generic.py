"""Country-agnostic PII regex patterns.

These target PII whose syntax is not country-specific, such as email, URL,
IPv4, and credit card. Pass them to a RegexDetector. Patterns match on shape
alone, with no checksum validation, so a value mangled by OCR is kept rather
than dropped.
"""

GENERIC_PATTERNS: dict[str, str] = {
    # Simplified RFC 5322, tight enough to avoid matching everything with an "@".
    "EMAIL": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    # Plain http(s) URL. The final character class excludes trailing sentence
    # punctuation, so a URL ending a sentence does not swallow the "." or ",".
    "URL": r"https?://[^\s<>\"']*[^\s<>\"'.,;:!?)\]]",
    # IPv4 with a per-octet 0-255 constraint.
    "IPV4": (
        r"(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
    ),
    # 13 to 19 digits with optional spaces or dashes. Matches on shape alone.
    "CREDIT_CARD": r"\b(?:\d[ -]?){12,18}\d\b",
}

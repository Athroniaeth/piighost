"""Pan-European PII regex patterns.

Targets values standardised across EU member states, such as the ISO 13616
IBAN. For country-specific numbers use the per-country packs instead. Pass them
to a RegexDetector.
"""

EU_PATTERNS: dict[str, str] = {
    # Generic IBAN, 2-letter country, 2 check digits, 11 to 30 alphanumerics.
    "IBAN": r"\b[A-Z]{2}\d{2}(?:[\s-]?[A-Z0-9]){11,30}\b",
}
"""Pan-European PII patterns (generic ISO 13616 IBAN) shared across EU member states."""

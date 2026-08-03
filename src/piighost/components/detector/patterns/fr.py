"""French PII regex patterns.

Labels are prefixed with FR_ so they do not collide with US or pan-EU packs.
Pass them to a RegexDetector. The IBAN and NIR patterns match on structure
alone, with no checksum validation.
"""

FR_PATTERNS: dict[str, str] = {
    # +33 or 0 prefix, 1-digit area code, then four pairs. Uses (?<!\d) and
    # (?!\d) because \b does not match between a non-word char and "+".
    "FR_PHONE": r"(?<!\d)(?:\+33|0)[1-9](?:[\s.-]?\d{2}){4}(?!\d)",
    # IBAN FR, FR + 2 check digits + 23 alphanumerics, optional separators.
    "FR_IBAN": r"\bFR\d{2}(?:[\s-]?[A-Z0-9]){23}\b",
    # NIR, sex + YY + MM + department + commune + order + key.
    "FR_NIR": (
        r"\b[12][\s.-]?\d{2}[\s.-]?(?:0[1-9]|1[0-2])[\s.-]?"
        r"(?:2A|2B|\d{2})[\s.-]?\d{3}[\s.-]?\d{3}[\s.-]?\d{2}\b"
    ),
    # SIRET, 9-digit SIREN + 5-digit establishment number, optional grouping.
    "FR_SIRET": r"\b\d{3}[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{5}\b",
}

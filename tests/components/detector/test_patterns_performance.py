"""Backtracking bounds for the regex pattern catalogs.

Every pattern is run against an adversarial text built to maximise backtracking,
a valid prefix followed by an endless repetition of the pattern's ambiguous
fragment and an ending that can never complete a match. A pattern whose scan is
quadratic in the input size blows the time budget; a linear one stays far under
it.
"""

import re
import time

import pytest

from piighost.components.detector.patterns import (
    EU_PATTERNS,
    FR_PATTERNS,
    GENERIC_PATTERNS,
    US_PATTERNS,
)

ALL_PATTERNS: dict[str, str] = {
    **GENERIC_PATTERNS,
    **US_PATTERNS,
    **EU_PATTERNS,
    **FR_PATTERNS,
}

_TEXT_LENGTH = 100_000
"""Adversarial text size in characters, the order of magnitude of a scanned page
batch and large enough for a quadratic scan to take seconds."""

_TIME_BUDGET = 0.1
"""Wall-clock budget in seconds for one findall over the adversarial text. A
linear pattern lands two orders of magnitude below it, so the margin absorbs a
slow CI runner without making the bound meaningless."""

_ADVERSARIAL_CASES: dict[str, tuple[str, str, str]] = {
    "EMAIL": ("john.doe@example.com ", "a.", "@"),
    "URL": ("https://", ".", " "),
    "IPV4": ("192.168.", "255.", "!"),
    "CREDIT_CARD": ("4111 1111 ", "1 ", "x"),
    "US_SSN": ("123-45-", "6", "x"),
    "US_PHONE": ("+1 (415) ", "555-", "x"),
    "US_ZIP": ("94103-", "1", "x"),
    "IBAN": ("GB82 ", "W1", "!"),
    "FR_PHONE": ("+33 6 ", "12 ", "x"),
    "FR_IBAN": ("FR76 ", "A1", "!"),
    "FR_NIR": ("1 85 01 ", "75 ", "x"),
    "FR_SIRET": ("123 456 ", "789 ", "x"),
}
"""Adversarial text recipe per label, as a valid prefix, the fragment repeated
to fill the text, and an ending that denies the match."""


def _adversarial_text(prefix: str, filler: str, suffix: str) -> str:
    """Build a text of about _TEXT_LENGTH characters from a case recipe."""
    room = _TEXT_LENGTH - len(prefix) - len(suffix)
    repeats = room // len(filler)
    return prefix + filler * repeats + suffix


def _findall_duration(pattern: str, text: str) -> float:
    """Compile a pattern and time a single findall over a text, in seconds."""
    compiled = re.compile(pattern)
    started = time.perf_counter()
    compiled.findall(text)
    return time.perf_counter() - started


class TestCoverage:
    def test_every_catalog_pattern_has_an_adversarial_case(self) -> None:
        """Each label of the four catalogs carries a backtracking case."""
        assert _ADVERSARIAL_CASES.keys() == ALL_PATTERNS.keys()


class TestBacktracking:
    @pytest.mark.parametrize(("label", "case"), _ADVERSARIAL_CASES.items())
    def test_scan_stays_within_the_time_budget(
        self, label: str, case: tuple[str, str, str]
    ) -> None:
        """A pattern scans an adversarial text of 100k characters in under 100ms."""
        prefix, filler, suffix = case
        text = _adversarial_text(prefix, filler, suffix)
        duration = _findall_duration(ALL_PATTERNS[label], text)
        assert duration < _TIME_BUDGET

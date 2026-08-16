"""Golden tests for the regex pattern catalogs.

Each pattern is checked against known true positives that must match in full
and true negatives that must not match. Resilience cases wrap a value in
adjacent punctuation and assert the detection covers the value alone, with the
trailing punctuation excluded.
"""

import pytest

from piighost.components.detector import RegexDetector
from piighost.components.detector.patterns import (
    EU_PATTERNS,
    FR_PATTERNS,
    GENERIC_PATTERNS,
    US_PATTERNS,
)
from piighost.models import Detection

ALL_PATTERNS: dict[str, str] = {
    **GENERIC_PATTERNS,
    **US_PATTERNS,
    **EU_PATTERNS,
    **FR_PATTERNS,
}

TRUE_POSITIVES: list[tuple[str, str]] = [
    ("EMAIL", "john.doe@example.com"),
    ("URL", "https://example.com/path?q=1"),
    ("IPV4", "192.168.0.1"),
    ("CREDIT_CARD", "4111 1111 1111 1111"),
    ("US_SSN", "123-45-6789"),
    ("US_PHONE", "+1 (415) 555-2671"),
    ("US_PHONE", "415-555-2671"),
    # A bare parenthesized area code is matched whole, parentheses included.
    ("US_PHONE", "(415) 555-2671"),
    ("US_ZIP", "94103-1234"),
    ("US_ZIP", "94103"),
    ("IBAN", "GB82WEST12345698765432"),
    ("FR_PHONE", "+33612345678"),
    ("FR_PHONE", "06 12 34 56 78"),
    ("FR_IBAN", "FR7630006000011234567890189"),
    ("FR_NIR", "180057505600157"),
    ("FR_SIRET", "73282932000074"),
]

TRUE_NEGATIVES: list[tuple[str, str]] = [
    ("EMAIL", "not an email"),
    ("EMAIL", "john@doe"),
    ("IPV4", "999.999.999.999"),
    ("US_SSN", "1234-56-789"),
    ("FR_PHONE", "0012345678"),
    # A URL needs an http(s) scheme; a bare host or another scheme is ignored.
    ("URL", "example.com"),
    ("URL", "ftp://example.com"),
    # A credit card is 13 to 19 digits; a short digit run is not one.
    ("CREDIT_CARD", "4111 1111"),
    # A ZIP is five digits; four is not one.
    ("US_ZIP", "1234"),
    # An IBAN needs a body of at least eleven alphanumerics after the prefix.
    ("IBAN", "DE44"),
    # A French IBAN must start with the literal FR country code.
    ("FR_IBAN", "DE7630006000011234567890189"),
    # A NIR month is 01 to 12; month 13 is rejected.
    ("FR_NIR", "180137505600157"),
    # A SIRET is fourteen digits; thirteen is not one.
    ("FR_SIRET", "7328293200007"),
]

# label, value, wrapper template with {v} where the value goes.
RESILIENCE_WRAPPERS: list[str] = [
    "{v}.",
    "{v},",
    "{v}\n",
    " {v} ",
    "({v})",
    "Reach me at {v}.",
]

RESILIENCE_VALUES: list[tuple[str, str]] = [
    ("EMAIL", "john.doe@example.com"),
    ("URL", "https://example.com/path?q=1"),
    ("IPV4", "192.168.0.1"),
    ("US_PHONE", "+1 (415) 555-2671"),
    ("FR_PHONE", "+33612345678"),
    ("IBAN", "GB82WEST12345698765432"),
]


async def _detect(label: str, text: str) -> list[Detection]:
    """Run a single-label RegexDetector over text and return its detections."""
    detector = RegexDetector({label: ALL_PATTERNS[label]})
    return await detector.detect(text)


class TestTruePositives:
    @pytest.mark.parametrize(("label", "value"), TRUE_POSITIVES)
    async def test_pattern_matches_the_whole_value(
        self, label: str, value: str
    ) -> None:
        """The pattern matches a known instance, covering the full value."""
        detections = await _detect(label, value)
        assert any(detection.text == value for detection in detections)


class TestTrueNegatives:
    @pytest.mark.parametrize(("label", "value"), TRUE_NEGATIVES)
    async def test_pattern_rejects_a_non_instance(self, label: str, value: str) -> None:
        """The pattern does not match a value that is not a real instance."""
        assert await _detect(label, value) == []


class TestResilience:
    @pytest.mark.parametrize(("label", "value"), RESILIENCE_VALUES)
    @pytest.mark.parametrize("wrapper", RESILIENCE_WRAPPERS)
    async def test_adjacent_punctuation_is_excluded(
        self, label: str, value: str, wrapper: str
    ) -> None:
        """A value wrapped in punctuation is detected without the punctuation."""
        text = wrapper.format(v=value)
        detections = await _detect(label, text)
        assert len(detections) == 1
        assert detections[0].text == value

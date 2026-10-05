"""Regex detector: find PII by matching configured patterns, one per label."""

import re
from typing import Self

from piighost.models import Detection, Span
from piighost.text import normalize_spaces


class RegexDetector:
    r"""Detector that finds PII by matching regex patterns, one per label.

    Each pattern is compiled once at construction, under re.ASCII, so the shape
    classes match ASCII only: \d is 0-9, not a Unicode digit shape such as an
    Arabic-Indic numeral, since a PII format uses ASCII digits and matching a
    look-alike would flag non-PII. detect emits one detection per non-overlapping
    match, at a flat confidence of 1.0. It carries no checksum validator and no
    optional dependency, so it stays cheap and matches on shape alone. A
    structured value mangled by OCR is kept rather than dropped, because dropping
    a real value would leak it.

    The patterns run on a copy of the text whose Unicode spaces are ordinary
    spaces, so a pattern written with " " or with \s also matches the no-break,
    thin or ideographic space a value is often typed with. The copy has the
    text's length, so each detection keeps its offsets and its text is sliced
    from the original, spaces as written.

    Attributes:
        patterns: Mapping of PII label to the regex pattern string to match.
    """

    @classmethod
    def from_catalog(cls, ref: str, *, catalog: str | None = None) -> Self:
        """Build a detector from the regexes a catalog reference carries.

        The catalog addresses a set of tested regexes by namespace/name and an
        optional selector, so RegexDetector.from_catalog("piighost/logs:fd79aec6")
        is the whole of what a caller needs to run a reviewed catalogue. A
        reference pinned to a commit is immutable and cached on disk; one
        pointing at a tag or at latest is fetched every time.

        Args:
            ref: A catalog reference, namespace/name with an optional :selector.
            catalog: Origin of the catalog to pull from. Defaults to the
                environment's PIIGHOST_CATALOG_URL, then to PIIGHOST_HUB_URL,
                then to the public catalog.

        Returns:
            A detector carrying the reference's patterns, in registry order.

        Raises:
            CatalogError: If the reference does not parse, the catalog cannot be
                reached, or what it returns is not a plain regex detector.
        """
        from piighost.catalog import pull

        return cls(pull(ref, catalog=catalog))

    @classmethod
    def from_hub(cls, ref: str, *, hub: str | None = None) -> Self:
        """The 1.x name of from_catalog, kept so code written for 1.8 and later runs.

        Args:
            ref: A catalog reference, namespace/name with an optional :selector.
            hub: Origin of the catalog to pull from, passed on as catalog=.
        """
        return cls.from_catalog(ref, catalog=hub)

    def __init__(self, patterns: dict[str, str]) -> None:
        """Compile every configured pattern under re.ASCII, keyed by its label."""
        self.patterns = patterns
        self._compiled: dict[str, re.Pattern[str]] = {
            label: re.compile(pattern, re.ASCII) for label, pattern in patterns.items()
        }

    async def detect(self, text: str) -> list[Detection]:
        """Return one detection per non-overlapping match of each pattern."""
        detections: list[Detection] = []
        searched = normalize_spaces(text)
        for label, compiled in self._compiled.items():
            for match in compiled.finditer(searched):
                span = Span(match.start(), match.end())
                detection = Detection(
                    span=span,
                    text=span.extract(text),
                    label=label,
                    confidence=1.0,
                )
                detections.append(detection)
        return detections

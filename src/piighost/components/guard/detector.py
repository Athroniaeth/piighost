"""Detector guard rail: re-run a detector and report residual PII."""

import copy
import re
from typing import Self

from piighost.components.detector.base import AnyDetector
from piighost.components.guard.base import GuardVerdict
from piighost.components.placeholder.base import BaseDelimitedPlaceholderFactory
from piighost.components.placeholder.streaming import (
    DEFAULT_PREFIX,
    DEFAULT_SUFFIX,
    compile_token_pattern,
)
from piighost.models import Detection

DEFAULT_PLACEHOLDER_PATTERN = compile_token_pattern(DEFAULT_PREFIX, DEFAULT_SUFFIX)
"""The grammar a guard with no recognizer finds placeholders with.

The default delimiters around a label with an optional identifier, so it matches
the tokens of every built-in delimited factory, <<PERSON>>, <<PERSON:1>> and
<<PERSON:a1b2c3d4>> alike.
"""

MIN_RESIDUAL_CHARACTERS = 2
"""Letters or digits a detection must keep outside placeholders to count.

Below two, what a detection holds beside its placeholders is punctuation or a
stray letter, such as the s of <<PERSON:1>>s, not a value.
"""

_WORD_CHARACTER = re.compile(r"[^\W_]")
"""One letter or digit, in any script."""


class DetectorGuardRail:
    """Re-run a detector on anonymized text and report any PII that remains.

    It scans the output with the given detector and flags the verdict when the
    detector finds a value, carrying what it found as the residual detections.
    This only adds value with a detector different from the pipeline's:
    re-running the same one finds nothing, since the pipeline already anonymized
    everything it detects. A stronger or complementary detector, run on the short
    anonymized output as a second pass, catches what a cheaper primary detector
    missed.

    A model-based detector often tags the placeholders themselves, reading
    <<PERSON:1>> as a person, which would flag every anonymized text. So by
    default the guard drops each detection that holds only placeholders: once the
    characters of the placeholders it covers are set aside, fewer than two letters
    or digits remain. A detection that keeps a value beside a placeholder, such as
    Dr Carter next to <<PERSON:1>>, still flags.

    Placeholders are found with the recognizer's grammar. Inside a pipeline, a
    guard given no recognizer takes the grammar of the tokens the pipeline emits.
    Used standalone, it falls back to the default delimited grammar.

    Attributes:
        detector: The detector re-run on the anonymized text.
        recognizer: The factory whose grammar finds the placeholders, or None for
            the pipeline's grammar, or the default one outside a pipeline.
        ignore_placeholders: Whether detections holding only placeholders are
            dropped before deciding. Turn it off to flag on every detection.
    """

    def __init__(
        self,
        detector: AnyDetector,
        recognizer: BaseDelimitedPlaceholderFactory | None = None,
        ignore_placeholders: bool = True,
    ) -> None:
        """Store the detector, the placeholder grammar, and the filter switch."""
        self.detector = detector
        self.recognizer = recognizer
        self.ignore_placeholders = ignore_placeholders

    def with_recognizer(self, recognizer: BaseDelimitedPlaceholderFactory) -> Self:
        """Return a copy of this guard finding placeholders with the given grammar.

        The pipeline calls it to hand its own grammar to a guard built without
        one, leaving the caller's guard unchanged.
        """
        bound = copy.copy(self)
        bound.recognizer = recognizer
        return bound

    async def check(self, text: str) -> GuardVerdict:
        """Return a verdict flagged when the detector finds a value in the text."""
        found = await self.detector.detect(text)
        residual = tuple(found)
        if self.ignore_placeholders:
            residual = self._beyond_placeholders(text, residual)
        return GuardVerdict(flagged=bool(residual), detections=residual)

    def _beyond_placeholders(
        self, text: str, detections: tuple[Detection, ...]
    ) -> tuple[Detection, ...]:
        """Keep the detections holding a value outside the placeholders.

        Placeholder positions are read from the whole text, so a detection that
        covers only part of a token, such as <<PERSON:8> without its last
        delimiter, is set aside as well.
        """
        covered: set[int] = set()
        pattern = self._placeholder_pattern()

        for match in pattern.finditer(text):
            covered.update(range(match.start(), match.end()))

        return tuple(
            detection
            for detection in detections
            if _residual_characters(text, detection, covered) >= MIN_RESIDUAL_CHARACTERS
        )

    def _placeholder_pattern(self) -> re.Pattern[str]:
        """The regex finding placeholders, the recognizer's or the default one."""
        if self.recognizer is None:
            return DEFAULT_PLACEHOLDER_PATTERN
        return self.recognizer.token_pattern


def _residual_characters(text: str, detection: Detection, covered: set[int]) -> int:
    """Count the letters and digits of a detection outside every placeholder."""
    span = detection.span
    return sum(
        1
        for index in range(span.start, span.end)
        if index not in covered and _WORD_CHARACTER.match(text[index])
    )

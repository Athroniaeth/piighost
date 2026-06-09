"""Guard rail stage: re-detection on the anonymized output.

A guard rail re-runs a detector on the anonymized text produced by the
pipeline.  If anything is still detected, the guard rail raises a
``PIIRemainingError``.  This catches cases where a misconfigured
detector, a NER miss, or a placeholder that did not match left raw
PII in the output.

The protocol is binary: pass or fail, no threshold to tune.  For a
graded view of remaining risk, see ``AnyRiskAssessor`` (roadmap).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Protocol

from piighost.detector import AnyDetector
from piighost.exceptions import PIIRemainingError
from piighost.models import Detection
from piighost.utils import boundary_wrap


def _has_uncovered_word_chars(
    start: int,
    end: int,
    text: str,
    spans: list[tuple[int, int]],
) -> bool:
    """Whether ``[start, end)`` contains word characters outside *spans*."""
    overlapping = sorted(
        (max(s, start), min(e, end)) for s, e in spans if s < end and e > start
    )
    cursor = start
    for s, e in overlapping:
        if cursor < s and re.search(r"\w", text[cursor:s]):
            return True
        cursor = max(cursor, e)
    return cursor < end and re.search(r"\w", text[cursor:end]) is not None


def filter_token_overlaps(
    detections: list[Detection],
    text: str,
    tokens: Sequence[str],
) -> list[Detection]:
    """Drop detections fully accounted for by known placeholder tokens.

    Guards re-run detectors on the anonymized output; with realistic
    factories (Faker) the placeholders themselves are detectable. The
    pipeline therefore forwards the tokens it just emitted, and
    detections covering only token occurrences are exempt from the
    residual-PII check.

    Token occurrences are located with word-boundary-anchored regex
    matching (see ``boundary_wrap``), so a token that is a strict
    substring of surrounding word characters does not count as an
    occurrence. A detection is dropped only if the part of its span not
    covered by token occurrences contains no word characters; trailing
    punctuation or whitespace from NER boundary slop is tolerated, but
    a detection spanning a token plus adjacent real PII is kept and the
    guard raises.

    Fail-closed consequences, both intended:

    - a token glued to a word character (e.g. ``<<PERSON:1>>123``) is
      not recognized as a token occurrence, so the overlapping
      detection is kept and the guard may raise a false alarm;
    - a detection containing no word characters at all (pure
      punctuation) is dropped whenever any token occurs in the text.

    Remaining accepted limitation: real PII whose text coincidentally
    equals a token string at another word-boundary position in the text
    is exempted; string-based matching cannot distinguish the two
    occurrences (``placeholder_tags`` already documents the Faker
    collision risk).

    Raises:
        TypeError: If *tokens* is a bare ``str``; a string would be
            iterated character by character and silently neutralize
            the residual-PII check.
    """
    if isinstance(tokens, str):
        raise TypeError(
            "tokens must be a sequence of token strings, not a bare str "
            "(a str would be iterated character by character and disable "
            "the residual-PII check)"
        )
    spans: list[tuple[int, int]] = []
    for token in tokens:
        if not token:
            continue
        for match in re.finditer(boundary_wrap(token), text):
            spans.append((match.start(), match.end()))
    if not spans:
        return list(detections)
    return [
        d
        for d in detections
        if _has_uncovered_word_chars(
            d.position.start_pos, d.position.end_pos, text, spans
        )
    ]


class AnyGuardRail(Protocol):
    """Protocol for the final pipeline stage.

    Implementations decide whether the anonymized text is safe to
    return.  ``check`` returns ``None`` on success and raises
    ``PIIRemainingError`` (or a subclass) on failure.
    """

    async def check(self, anonymized_text: str, tokens: Sequence[str] = ()) -> None:
        """Validate that ``anonymized_text`` no longer contains PII.

        Args:
            anonymized_text: The text produced by ``Anonymizer``.
            tokens: Placeholder tokens the pipeline emitted for this
                text; occurrences are exempt from the residual-PII check.

        Raises:
            PIIRemainingError: If residual PII is detected.
        """
        ...


class DisabledGuardRail:
    """Default no-op guard rail.

    Mirrors the ``Disabled*`` family used by the other pipeline stages
    so that pipelines built without a custom guard rail keep their
    current behaviour: the anonymized text is returned as-is.
    """

    async def check(self, anonymized_text: str, tokens: Sequence[str] = ()) -> None:
        return None


class DetectorGuardRail:
    """Guard rail backed by an ``AnyDetector``.

    Re-runs a detector on the anonymized output.  If the detector
    produces any detection, the guard rail raises
    ``PIIRemainingError`` carrying the residual detections so callers
    can log or surface them.

    The wrapped detector is independent from the pipeline detector:
    typical pairings include a strict regex detector after a permissive
    NER (catch leftover IBANs / emails the NER missed) or a tighter
    NER after a regex pass (catch unusual names).

    Args:
        detector: Any ``AnyDetector`` implementation.

    Example:
        >>> import asyncio
        >>> from piighost.detector.base import RegexDetector
        >>> guard = DetectorGuardRail(
        ...     detector=RegexDetector(patterns={"EMAIL": r"\\S+@\\S+"}),
        ... )
        >>> asyncio.run(guard.check("Hello <<PERSON:1>>"))  # passes
    """

    _detector: AnyDetector

    def __init__(self, detector: AnyDetector) -> None:
        self._detector = detector

    async def check(self, anonymized_text: str, tokens: Sequence[str] = ()) -> None:
        residual = await self._detector.detect(anonymized_text)
        residual = filter_token_overlaps(residual, anonymized_text, tokens)
        if residual:
            raise PIIRemainingError(
                f"{len(residual)} residual detection(s) found in anonymized text",
                detections=list(residual),
            )


__all__ = [
    "AnyGuardRail",
    "DetectorGuardRail",
    "DisabledGuardRail",
    "filter_token_overlaps",
]
